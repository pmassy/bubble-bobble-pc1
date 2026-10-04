from PIL import Image
import argparse
import colorsys
import math
import sys

# Palette PC1 fissa: indice 0..15
PC1 = [
    (0, 0, 0),        # 0 black
    (0, 0, 160),      # 1 blue
    (0, 160, 0),      # 2 green
    (0, 160, 160),    # 3 cyan
    (160, 0, 0),      # 4 red
    (128, 0, 160),    # 5 purple
    (160, 80, 0),     # 6 brown/orange
    (160, 160, 160),  # 7 light gray
    (80, 80, 80),     # 8 dark gray
    (80, 80, 255),    # 9 light blue
    (0, 255, 80),     # A light green
    (80, 255, 255),   # B light cyan
    (255, 80, 80),    # C light red
    (255, 80, 255),   # D light magenta
    (255, 255, 80),   # E yellow
    (255, 255, 255),  # F white
]

# Colori C64 tipici usati negli asset del repository -> indice PC1 desiderato.
# Questo evita i casi in cui un colore saturo finisce su un grigio solo
# perché è "più vicino" numericamente in RGB.
C64_EXACT = {
    (0x00, 0x00, 0x00): 0,   # black
    (0xFF, 0xFF, 0xFF): 15,  # white
    (0x81, 0x33, 0x38): 4,   # red
    (0x75, 0xCE, 0xC8): 11,  # cyan
    (0x8E, 0x3C, 0x97): 5,   # purple
    (0x56, 0xAC, 0x4D): 2,   # green
    (0x2E, 0x2C, 0x9B): 1,   # blue
    (0xED, 0xF1, 0x71): 14,  # yellow
    (0x8E, 0x50, 0x29): 6,   # orange
    (0x55, 0x38, 0x00): 6,   # brown
    (0xC4, 0x6C, 0x71): 12,  # light red
    (0x4A, 0x4A, 0x4A): 8,   # dark gray
    (0x7B, 0x7B, 0x7B): 7,   # gray
    (0xA9, 0xFF, 0x9F): 10,  # light green
    (0x70, 0x6D, 0xEB): 9,   # light blue
    (0xB2, 0xB2, 0xB2): 7,   # light gray
}

GRAY_INDICES = {0, 7, 8, 15}

def rgb_to_hsv255(rgb):
    r, g, b = (v / 255.0 for v in rgb)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360.0, s, v

def hue_distance(a, b):
    d = abs(a - b)
    return min(d, 360.0 - d)

def semantic_distance(src, dst, dst_index):
    """
    Distanza pensata per pixel-art:
    - preserva prima di tutto "colorato vs grigio"
    - poi tonalità (hue)
    - infine luminosità/saturazione.
    Questo evita cyan/rosso/marrone -> grigio.
    """
    sh, ss, sv = rgb_to_hsv255(src)
    dh, ds, dv = rgb_to_hsv255(dst)

    # Se il sorgente è chiaramente saturo, penalizza fortemente i grigi.
    gray_penalty = 0.0
    if ss >= 0.22 and dst_index in GRAY_INDICES:
        gray_penalty = 5000.0

    # Se il sorgente è quasi grigio, preferisci i grigi.
    chroma_penalty = 0.0
    if ss < 0.12 and dst_index not in GRAY_INDICES:
        chroma_penalty = 2500.0

    # Per colori saturi, l'hue deve pesare molto.
    if ss >= 0.12 and ds >= 0.05:
        hd = hue_distance(sh, dh) / 180.0
    else:
        hd = 0.0

    sat_d = ss - ds
    val_d = sv - dv

    # RGB serve solo come rifinitura.
    dr = (src[0] - dst[0]) / 255.0
    dg = (src[1] - dst[1]) / 255.0
    db = (src[2] - dst[2]) / 255.0
    rgb_d = dr*dr + dg*dg + db*db

    return (
        gray_penalty
        + chroma_penalty
        + 3500.0 * hd * hd
        + 450.0 * sat_d * sat_d
        + 350.0 * val_d * val_d
        + 100.0 * rgb_d
    )

def nearest_pc1(rgb):
    # 1) match esatto dei colori C64 che conosciamo
    if rgb in C64_EXACT:
        return C64_EXACT[rgb]

    # 2) match semantico/hue-aware sui 16 colori PC1
    best_i = 0
    best_d = None
    for i, c in enumerate(PC1):
        d = semantic_distance(rgb, c, i)
        if best_d is None or d < best_d:
            best_d = d
            best_i = i
    return best_i

def make_palette_768():
    p = []
    for rgb in PC1:
        p.extend(rgb)
    p.extend([0] * (768 - len(p)))
    return p

def main():
    ap = argparse.ArgumentParser(
        description="Converte un'immagine ai 16 indici PC1 con mapping colore più robusto."
    )
    ap.add_argument("input", help="PNG/TGA/BMP sorgente")
    ap.add_argument("output", nargs="?", default="BBLOCKS_160x200px_INDEXED.png")
    args = ap.parse_args()

    src = Image.open(args.input).convert("RGBA")
    if src.size != (160, 200):
        raise ValueError(f"Dimensioni {src.size}, attese 160x200")

    out = Image.new("P", src.size)
    out.putpalette(make_palette_768())

    cache = {}
    converted = []
    counts = [0] * 16

    for r, g, b, a in src.getdata():
        if a == 0:
            rgb = (0, 0, 0)
        else:
            rgb = (r, g, b)

        if rgb not in cache:
            cache[rgb] = nearest_pc1(rgb)

        idx = cache[rgb]
        converted.append(idx)
        counts[idx] += 1

    out.putdata(converted)
    out.save(args.output, format="PNG", optimize=False)

    used = [i for i, n in enumerate(counts) if n]
    print(f"Input:  {args.input}")
    print(f"Output: {args.output}")
    print(f"Mode:   P")
    print(f"Indici usati: {[f'{i:X}' for i in used]}")
    print("Pixel per indice:")
    for i in used:
        print(f"  {i:X}: {counts[i]:6d}   RGB={PC1[i]}")
    print("OK")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        sys.exit(1)
