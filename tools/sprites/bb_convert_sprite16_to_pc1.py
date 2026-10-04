from pathlib import Path
import argparse
import shutil
import sys
from PIL import Image

# Palette logica 16 colori usata solo come fallback RGB.
# Se il PNG è indicizzato (mode P), usiamo direttamente gli indici 0..15.
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
    (85, 255, 85),     # 10
    (85, 255, 255),    # 11
    (255, 85, 85),     # 12
    (255, 85, 255),    # 13
    (255, 255, 85),    # 14
    (255, 255, 255),   # 15
]

# Palette visuale del PNG di uscita (gli indici contano più dei colori visuali)
PALETTE4 = [
    (0, 0, 0),         # 0
    (0, 255, 255),     # 1
    (255, 0, 255),     # 2
    (255, 255, 255),   # 3
]


def nearest_16_index(rgb):
    r, g, b = rgb
    best_i = 0
    best_d = None
    for i, (pr, pg, pb) in enumerate(PALETTE16):
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if best_d is None or d < best_d:
            best_d = d
            best_i = i
    return best_i


def build_palette_bytes(palette):
    flat = []
    for rgb in palette:
        flat.extend(rgb)
    flat.extend([0, 0, 0] * (256 - len(palette)))
    return flat


def read_logical_indices(img, force_rgb=False):
    """
    Ritorna una lista di indici logici 0..15, uno per pixel.
    Se il file è indicizzato (P) e non c'è force_rgb, usa direttamente gli indici.
    Altrimenti fa un nearest-color sulla palette 16.
    """
    if img.mode == "P" and not force_rgb:
        idx = list(img.getdata())
        for v in idx:
            if not (0 <= v <= 15):
                raise ValueError(f"trovato indice fuori range 0..15: {v}")
        return idx, "indexed"

    rgb = img.convert("RGB")
    idx = [nearest_16_index(px) for px in rgb.getdata()]
    return idx, "rgb"


def convert_phase_image(src_path, dst_path, force_rgb=False, strict_pairs=False):
    img = Image.open(src_path)
    w, h = img.size

    if w % 2 != 0:
        raise ValueError(f"{src_path}: larghezza dispari ({w}), servono coppie orizzontali.")

    logical, mode_used = read_logical_indices(img, force_rgb=force_rgb)

    out = Image.new("P", (w, h))
    out.putpalette(build_palette_bytes(PALETTE4))

    out_pixels = []
    mismatches = 0

    for y in range(h):
        row = logical[y * w:(y + 1) * w]

        for x in range(0, w, 2):
            a = row[x]
            b = row[x + 1]

            if a != b:
                mismatches += 1
                if strict_pairs:
                    raise ValueError(
                        f"{src_path}: coppia non uniforme a x={x}, y={y} ({a} != {b})"
                    )
                # Se la coppia non è uniforme, prendiamo il primo pixel come colore logico
                logical_color = a
            else:
                logical_color = a

            if not (0 <= logical_color <= 15):
                raise ValueError(
                    f"{src_path}: colore logico fuori range 0..15: {logical_color}"
                )

            left = logical_color // 4
            right = logical_color % 4

            out_pixels.append(left)
            out_pixels.append(right)

    out.putdata(out_pixels)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst_path)

    return {
        "mode": mode_used,
        "size": (w, h),
        "mismatches": mismatches,
    }


def is_phase_image(path: Path):
    name = path.name.lower()
    return name.startswith("phase_") and name.endswith("_image.png")


def main():
    ap = argparse.ArgumentParser(
        description="Converte sprite 16 colori logici in PNG CGA-coded per SPRITES.CCF."
    )
    ap.add_argument("input_dir", help="Cartella sorgente, es. work_ccf_16\\sprites")
    ap.add_argument("output_dir", help="Cartella destinazione, es. work_ccf_pc1\\sprites")
    ap.add_argument(
        "--force-rgb",
        action="store_true",
        help="Ignora gli indici del PNG e ricava i colori facendo nearest-color sulla palette 16."
    )
    ap.add_argument(
        "--strict-pairs",
        action="store_true",
        help="Errore se una coppia orizzontale non ha due pixel uguali."
    )
    args = ap.parse_args()

    src_root = Path(args.input_dir)
    dst_root = Path(args.output_dir)

    if not src_root.is_dir():
        print(f"ERRORE: cartella input non trovata: {src_root}")
        sys.exit(1)

    converted = 0
    copied = 0
    total_mismatches = 0

    for src in src_root.rglob("*"):
        rel = src.relative_to(src_root)
        dst = dst_root / rel

        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue

        if is_phase_image(src):
            info = convert_phase_image(
                src, dst,
                force_rgb=args.force_rgb,
                strict_pairs=args.strict_pairs
            )
            converted += 1
            total_mismatches += info["mismatches"]
            print(
                f"CONVERTITO: {rel} | {info['size'][0]}x{info['size'][1]} | "
                f"mode={info['mode']} | coppie non uniformi={info['mismatches']}"
            )
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
            print(f"COPIATO:    {rel}")

    print()
    print("========================================")
    print("Conversione completata")
    print("========================================")
    print(f"Cartella input:       {src_root}")
    print(f"Cartella output:      {dst_root}")
    print(f"Image convertite:     {converted}")
    print(f"File copiati:         {copied}")
    print(f"Coppie non uniformi:  {total_mismatches}")


if __name__ == "__main__":
    main()