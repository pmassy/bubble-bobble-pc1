# bb_mark_duplicate_sprites.py
# Analizza gli sprite estratti e marca i duplicati in un mega sheet annotato.
#
# Default: confronta i file phase_*_image.png
#
# Output:
# - sprites_duplicates_annotated.png
# - sprites_duplicates_report.txt
# - sprites_duplicates.csv

import os
import re
import csv
import math
import hashlib
import argparse
from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont

BLOCK_RE = re.compile(r"block_(\d+)$", re.IGNORECASE)
PHASE_RE = re.compile(r"phase_(\d+)_(image|mask|composed)\.png$", re.IGNORECASE)

def block_key(name):
    m = BLOCK_RE.match(name)
    return int(m.group(1)) if m else 999999

def phase_key(name):
    m = PHASE_RE.match(name)
    if not m:
        return (999999, name.lower())
    return (int(m.group(1)), m.group(2).lower())

def sha1_image(img):
    # Usiamo RGBA per confronto rigoroso
    rgba = img.convert("RGBA")
    h = hashlib.sha1()
    h.update(str(rgba.size).encode("ascii"))
    h.update(rgba.tobytes())
    return h.hexdigest()

def load_entries(root, kind="image"):
    entries = []
    blocks = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)) and BLOCK_RE.match(d)]
    blocks.sort(key=block_key)

    for block_name in blocks:
        block_path = os.path.join(root, block_name)
        files = [f for f in os.listdir(block_path) if f.lower().endswith(".png")]
        files.sort(key=phase_key)

        for fname in files:
            m = PHASE_RE.match(fname)
            if not m:
                continue
            phase_num = int(m.group(1))
            phase_kind = m.group(2).lower()
            if phase_kind != kind:
                continue

            path = os.path.join(block_path, fname)
            entries.append({
                "block_name": block_name,
                "block_num": block_key(block_name),
                "phase_num": phase_num,
                "kind": phase_kind,
                "filename": fname,
                "path": path,
            })
    return entries

def analyze_duplicates(entries):
    groups = {}
    group_members = defaultdict(list)
    group_first = {}
    analyzed = []

    group_counter = 1

    for idx, e in enumerate(entries):
        img = Image.open(e["path"])
        digest = sha1_image(img)

        if digest not in groups:
            gid = group_counter
            group_counter += 1
            groups[digest] = gid
            group_first[gid] = idx
        else:
            gid = groups[digest]

        info = dict(e)
        info["digest"] = digest
        info["group_id"] = gid
        info["size"] = img.size
        analyzed.append(info)
        group_members[gid].append(info)

    return analyzed, group_members, group_first

def get_font():
    try:
        return ImageFont.truetype("arial.ttf", 12)
    except:
        return ImageFont.load_default()

def make_annotated_sheet(analyzed, group_members, group_first, out_png):
    if not analyzed:
        raise RuntimeError("Nessuno sprite trovato.")

    blocks = sorted({e["block_num"] for e in analyzed})
    max_phase = max(e["phase_num"] for e in analyzed)

    # mappa (block, phase) -> entry
    grid = {}
    max_w = 0
    max_h = 0

    for e in analyzed:
        img = Image.open(e["path"])
        grid[(e["block_num"], e["phase_num"])] = e
        w, h = img.size
        max_w = max(max_w, w)
        max_h = max(max_h, h)

    font = get_font()
    label_h = 16
    pad = 6
    cell_w = max_w + pad * 2
    cell_h = max_h + label_h + pad * 2

    left_header_w = 90
    top_header_h = 24

    sheet_w = left_header_w + (max_phase + 1) * cell_w
    sheet_h = top_header_h + len(blocks) * cell_h

    sheet = Image.new("RGB", (sheet_w, sheet_h), (32, 32, 32))
    draw = ImageDraw.Draw(sheet)

    # intestazione fasi
    for ph in range(max_phase + 1):
        x0 = left_header_w + ph * cell_w
        draw.rectangle([x0, 0, x0 + cell_w - 1, top_header_h - 1], outline=(90, 90, 90), fill=(45, 45, 45))
        draw.text((x0 + 6, 5), f"ph {ph}", fill=(255, 255, 255), font=font)

    # righe blocchi
    for row, block_num in enumerate(blocks):
        y0 = top_header_h + row * cell_h
        draw.rectangle([0, y0, left_header_w - 1, y0 + cell_h - 1], outline=(90, 90, 90), fill=(45, 45, 45))
        draw.text((6, y0 + 6), f"block_{block_num:04d}", fill=(255, 255, 255), font=font)

        for ph in range(max_phase + 1):
            x0 = left_header_w + ph * cell_w
            draw.rectangle([x0, y0, x0 + cell_w - 1, y0 + cell_h - 1], outline=(70, 70, 70), fill=(24, 24, 24))

            e = grid.get((block_num, ph))
            if not e:
                continue

            img = Image.open(e["path"]).convert("RGBA")
            gid = e["group_id"]
            members = group_members[gid]
            first_entry = members[0]
            first_is_this = (first_entry["block_num"] == e["block_num"] and first_entry["phase_num"] == e["phase_num"])

            # classificazione grafica
            if len(members) == 1:
                border = (0, 180, 0)       # unico
                tag = f"U{gid:03d}"
            else:
                if first_is_this:
                    border = (0, 140, 220)  # master di gruppo duplicato
                    tag = f"M{gid:03d}"
                else:
                    border = (220, 60, 60)  # duplicato
                    tag = f"D{gid:03d}"

            # bordo interno cella
            draw.rectangle([x0 + 1, y0 + 1, x0 + cell_w - 2, y0 + cell_h - 2], outline=border)

            # incolla immagine centrata
            px = x0 + (cell_w - img.width) // 2
            py = y0 + label_h + pad + (max_h - img.height) // 2
            sheet.paste(img.convert("RGB"), (px, py))

            # etichetta
            draw.rectangle([x0 + 2, y0 + 2, x0 + cell_w - 3, y0 + label_h], fill=(0, 0, 0))
            draw.text((x0 + 5, y0 + 4), tag, fill=border, font=font)

    sheet.save(out_png)

def write_report(analyzed, group_members, out_txt, out_csv):
    total = len(analyzed)
    unique_groups = len(group_members)
    duplicate_count = total - unique_groups

    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("ANALISI DUPLICATI SPRITE\n")
        f.write("=" * 40 + "\n\n")
        f.write(f"Totale sprite analizzati : {total}\n")
        f.write(f"Sprite unici             : {unique_groups}\n")
        f.write(f"Duplicati                : {duplicate_count}\n\n")

        f.write("Legenda:\n")
        f.write(" Uxxx = sprite unico\n")
        f.write(" Mxxx = master (prima occorrenza di un gruppo con duplicati)\n")
        f.write(" Dxxx = duplicato del gruppo xxx\n\n")

        f.write("GRUPPI\n")
        f.write("-" * 40 + "\n")

        for gid in sorted(group_members.keys()):
            members = group_members[gid]
            kind = "UNICO" if len(members) == 1 else f"DUPLICATI ({len(members)} occorrenze)"
            f.write(f"\nGruppo {gid:03d} - {kind}\n")
            for i, e in enumerate(members):
                prefix = "MASTER" if i == 0 and len(members) > 1 else "ITEM"
                f.write(f"  {prefix:6s}  {e['block_name']}  phase_{e['phase_num']}_{e['kind']}.png\n")

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f, delimiter=";")
        wr.writerow(["block", "phase", "kind", "group_id", "role"])
        for gid in sorted(group_members.keys()):
            members = group_members[gid]
            for i, e in enumerate(members):
                if len(members) == 1:
                    role = "UNIQUE"
                else:
                    role = "MASTER" if i == 0 else "DUPLICATE"
                wr.writerow([e["block_name"], e["phase_num"], e["kind"], f"{gid:03d}", role])

def main():
    ap = argparse.ArgumentParser(description="Annota i duplicati degli sprite estratti.")
    ap.add_argument("sprites_root", help="Cartella root sprites, es: work_ccf_pc1\\sprites")
    ap.add_argument("--kind", default="image", choices=["image", "mask", "composed"],
                    help="Tipo di file da analizzare (default: image)")
    ap.add_argument("--out-sheet", default="sprites_duplicates_annotated.png",
                    help="PNG annotato in output")
    ap.add_argument("--out-report", default="sprites_duplicates_report.txt",
                    help="Report testuale")
    ap.add_argument("--out-csv", default="sprites_duplicates.csv",
                    help="CSV con mapping gruppi")
    args = ap.parse_args()

    entries = load_entries(args.sprites_root, kind=args.kind)
    if not entries:
        raise SystemExit("Nessun file trovato del tipo richiesto.")

    analyzed, group_members, group_first = analyze_duplicates(entries)
    make_annotated_sheet(analyzed, group_members, group_first, args.out_sheet)
    write_report(analyzed, group_members, args.out_report, args.out_csv)

    total = len(analyzed)
    unique_groups = len(group_members)
    duplicate_count = total - unique_groups

    print("=" * 50)
    print("Analisi completata")
    print("=" * 50)
    print(f"Cartella sprite:   {args.sprites_root}")
    print(f"Tipo analizzato:   {args.kind}")
    print(f"Totale sprite:     {total}")
    print(f"Sprite unici:      {unique_groups}")
    print(f"Duplicati:         {duplicate_count}")
    print(f"Sheet annotato:    {args.out_sheet}")
    print(f"Report:            {args.out_report}")
    print(f"CSV:               {args.out_csv}")

if __name__ == "__main__":
    main()