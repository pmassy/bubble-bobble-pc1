from pathlib import Path
from PIL import Image
import argparse
import csv
import shutil
import sys

# Deve essere IDENTICA alla palette logica usata da bb_convert_sprite16_to_pc1.py
PALETTE16 = [
    (0, 0, 0),         # 0
    (0, 0, 170),       # 1
    (0, 170, 0),       # 2
    (0, 170, 170),     # 3
    (170, 0, 0),       # 4
    (170, 0, 170),     # 5
    (170, 85, 0),      # 6
    (170, 170, 170),   # 7
    (85, 85, 85),      # 8
    (85, 85, 255),     # 9
    (85, 255, 85),     # A
    (85, 255, 255),    # B
    (255, 85, 85),     # C
    (255, 85, 255),    # D
    (255, 255, 85),    # E
    (255, 255, 255),   # F
]

# Geometria usata da bb_mark_duplicate_sprites.py
LABEL_H = 16
PAD = 6
LEFT_HEADER_W = 90
TOP_HEADER_H = 24

def palette_flat():
    p = []
    for rgb in PALETTE16:
        p.extend(rgb)
    p.extend([0, 0, 0] * (256 - len(PALETTE16)))
    return p

PAL16_FLAT = palette_flat()

def nearest16(rgb):
    r, g, b = rgb
    best_i = 0
    best_d = None
    for i, (pr, pg, pb) in enumerate(PALETTE16):
        d = (r-pr)**2 + (g-pg)**2 + (b-pb)**2
        if best_d is None or d < best_d:
            best_d = d
            best_i = i
    return best_i

def force_logical16(img):
    """
    Converte il ritaglio RGB del mega-sheet in PNG P con indici 0..15.
    Nessun dithering: ogni pixel va al colore logico PC1 più vicino.
    """
    rgb = img.convert("RGB")
    out = Image.new("P", rgb.size)
    out.putpalette(PAL16_FLAT)
    out.putdata([nearest16(px) for px in rgb.getdata()])
    return out

def make_mask_from_logical(img_p):
    """
    Regola richiesta:
      indice/colore nero -> mask nera
      qualunque pixel non nero -> mask bianca
    """
    vals = list(img_p.getdata())
    out = Image.new("P", img_p.size)
    pal = [0,0,0, 255,255,255] + [0,0,0] * 254
    out.putpalette(pal)
    out.putdata([0 if v == 0 else 1 for v in vals])
    return out

def block_num(name):
    try:
        return int(name.split("_")[1])
    except Exception:
        return 999999

def phase_path(root, block, phase, kind="image"):
    return root / block / f"phase_{phase}_{kind}.png"

def scan_geometry(sprites_root):
    blocks = sorted(
        [p for p in sprites_root.iterdir() if p.is_dir() and p.name.startswith("block_")],
        key=lambda p: block_num(p.name)
    )
    if not blocks:
        raise RuntimeError(f"Nessun block_* in {sprites_root}")

    block_names = [p.name for p in blocks]
    max_w = 0
    max_h = 0
    max_phase = -1
    sizes = {}

    for bdir in blocks:
        for p in bdir.glob("phase_*_image.png"):
            try:
                ph = int(p.name.split("_")[1])
            except Exception:
                continue
            with Image.open(p) as im:
                w, h = im.size
            sizes[(bdir.name, ph)] = (w, h)
            max_w = max(max_w, w)
            max_h = max(max_h, h)
            max_phase = max(max_phase, ph)

    if max_phase < 0:
        raise RuntimeError("Nessun phase_*_image.png trovato")

    cell_w = max_w + PAD * 2
    cell_h = max_h + LABEL_H + PAD * 2
    sheet_w = LEFT_HEADER_W + (max_phase + 1) * cell_w
    sheet_h = TOP_HEADER_H + len(block_names) * cell_h

    return {
        "blocks": block_names,
        "row_of": {b:i for i,b in enumerate(block_names)},
        "sizes": sizes,
        "max_w": max_w,
        "max_h": max_h,
        "max_phase": max_phase,
        "cell_w": cell_w,
        "cell_h": cell_h,
        "sheet_w": sheet_w,
        "sheet_h": sheet_h,
    }

def read_mapping(csv_path):
    rows = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f, delimiter=";")
        needed = {"block","phase","kind","group_id","role"}
        if not rd.fieldnames or not needed.issubset(set(rd.fieldnames)):
            raise ValueError(
                f"CSV non riconosciuto. Attese colonne: {sorted(needed)}; "
                f"trovate: {rd.fieldnames}"
            )
        for r in rd:
            if r["kind"].lower() != "image":
                continue
            rows.append({
                "block": r["block"],
                "phase": int(r["phase"]),
                "group_id": r["group_id"],
                "role": r["role"].upper(),
            })

    groups = {}
    for r in rows:
        groups.setdefault(r["group_id"], []).append(r)

    # Ogni gruppo deve avere esattamente una sorgente editabile:
    # UNIQUE oppure MASTER.
    sources = {}
    for gid, members in groups.items():
        candidates = [m for m in members if m["role"] in ("UNIQUE","MASTER")]
        if len(candidates) != 1:
            raise ValueError(
                f"Gruppo {gid}: atteso 1 MASTER/UNIQUE, trovati {len(candidates)}"
            )
        sources[gid] = candidates[0]

    return rows, groups, sources

def crop_entry(sheet, geom, block, phase):
    key = (block, phase)
    if key not in geom["sizes"]:
        raise KeyError(f"Sprite non esistente nella baseline: {block} phase {phase}")

    w, h = geom["sizes"][key]
    row = geom["row_of"][block]

    x0 = LEFT_HEADER_W + phase * geom["cell_w"]
    y0 = TOP_HEADER_H + row * geom["cell_h"]

    # Identica posizione usata dal packer.
    px = x0 + (geom["cell_w"] - w) // 2
    py = y0 + LABEL_H + PAD + (geom["max_h"] - h) // 2

    return sheet.crop((px, py, px + w, py + h))

def copy_baseline(src_root, dst_root, clean):
    if clean and dst_root.exists():
        shutil.rmtree(dst_root)
    if dst_root.exists():
        raise FileExistsError(
            f"{dst_root} esiste già. Usa --clean oppure scegli un'altra cartella."
        )
    shutil.copytree(src_root, dst_root)

def main():
    ap = argparse.ArgumentParser(
        description="Reimporta il mega-sheet annotato modificato nelle cartelle SPRITES."
    )
    ap.add_argument("edited_sheet", help="Mega PNG modificato DAL GRAFICO, a risoluzione originale")
    ap.add_argument("baseline_sprites", help=r"Cartella sprites vergine, es. work_ccf_16\sprites")
    ap.add_argument("mapping_csv", help="CSV GENERATO INSIEME AL MEGA-SHEET MODIFICATO")
    ap.add_argument("output_sprites", help=r"Output, es. work_ccf_reimport\sprites")
    ap.add_argument("--clean", action="store_true", help="Cancella output_sprites se esiste")
    args = ap.parse_args()

    sheet_path = Path(args.edited_sheet)
    base_root = Path(args.baseline_sprites)
    csv_path = Path(args.mapping_csv)
    out_root = Path(args.output_sprites)

    if not sheet_path.is_file():
        raise FileNotFoundError(sheet_path)
    if not base_root.is_dir():
        raise FileNotFoundError(base_root)
    if not csv_path.is_file():
        raise FileNotFoundError(csv_path)

    geom = scan_geometry(base_root)
    rows, groups, sources = read_mapping(csv_path)

    sheet = Image.open(sheet_path).convert("RGB")

    expected = (geom["sheet_w"], geom["sheet_h"])
    if sheet.size != expected:
        raise ValueError(
            "\nDIMENSIONI MEGA-SHEET NON CORRETTE.\n"
            f"File:     {sheet.size[0]}x{sheet.size[1]}\n"
            f"Attese:   {expected[0]}x{expected[1]}\n\n"
            "NON ridimensionare il file per farlo accettare.\n"
            "Serve il PNG originale a piena risoluzione generato dallo script."
        )

    copy_baseline(base_root, out_root, args.clean)

    converted_sources = {}
    quantization_changed = 0

    # 1) Estrai una sola volta ogni MASTER/UNIQUE.
    for gid, src in sources.items():
        crop = crop_entry(sheet, geom, src["block"], src["phase"])
        logical = force_logical16(crop)
        converted_sources[gid] = logical

    # 2) Propaga il MASTER/UNIQUE a TUTTE le occorrenze del gruppo.
    written = 0
    masks = 0

    for gid, members in groups.items():
        logical_master = converted_sources[gid]
        master_size = logical_master.size

        for m in members:
            key = (m["block"], m["phase"])
            expected_size = geom["sizes"].get(key)
            if expected_size is None:
                raise KeyError(f"CSV punta a sprite inesistente: {key}")
            if expected_size != master_size:
                raise ValueError(
                    f"Gruppo {gid}: dimensioni diverse: master {master_size}, "
                    f"{m['block']} phase {m['phase']} = {expected_size}"
                )

            ipath = phase_path(out_root, m["block"], m["phase"], "image")
            mpath = phase_path(out_root, m["block"], m["phase"], "mask")

            logical_master.save(ipath)
            mask = make_mask_from_logical(logical_master)
            mask.save(mpath)

            written += 1
            masks += 1

    report = out_root.parent / "reimport_sheet_report.txt"
    with report.open("w", encoding="utf-8") as f:
        f.write("REIMPORT MEGA-SHEET COMPLETATO\n")
        f.write("========================================\n")
        f.write(f"Sheet: {sheet_path}\n")
        f.write(f"Dimensioni sheet: {sheet.size[0]}x{sheet.size[1]}\n")
        f.write(f"Baseline: {base_root}\n")
        f.write(f"CSV: {csv_path}\n")
        f.write(f"Output: {out_root}\n")
        f.write(f"Gruppi/master estratti: {len(converted_sources)}\n")
        f.write(f"phase image scritte: {written}\n")
        f.write(f"mask rigenerate: {masks}\n")
        f.write("\n")
        f.write("NOTA: i DUPLICATE sono stati sovrascritti con il relativo MASTER.\n")
        f.write("La palette di ogni phase_*_image.png è logical16 PC1.\n")

    print()
    print("========================================")
    print("REIMPORT COMPLETATO")
    print("========================================")
    print(f"Mega-sheet:              {sheet_path}")
    print(f"Dimensioni verificate:   {sheet.size[0]}x{sheet.size[1]}")
    print(f"Gruppi editabili:        {len(converted_sources)}")
    print(f"Sprite scritti:          {written}")
    print(f"Mask generate:           {masks}")
    print(f"Output:                   {out_root}")
    print(f"Report:                   {report}")
    print()
    print("PASSO SUCCESSIVO:")
    print("  py bb_convert_sprite16_to_pc1.py <output_sprites> work_ccf_pc1\\sprites")
    print()
    print("Poi ricostruisci SPRITES.CCF con --import-masks.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        sys.exit(1)
