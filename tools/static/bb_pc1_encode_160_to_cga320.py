from pathlib import Path
from PIL import Image
import argparse
import sys


# Palette logica 16 colori usata dal PNG 160x200
DOS16 = [
    (0,   0,   0),     # 0  nero
    (0,   0, 160),     # 1  blu
    (0, 160,   0),     # 2  verde
    (0, 160, 160),     # 3  ciano
    (160, 0,   0),     # 4  rosso scuro
    (128, 0, 160),     # 5  viola
    (160, 80,  0),     # 6  marrone/arancio
    (160, 160, 160),   # 7  grigio chiaro
    (80,  80,  80),    # 8  grigio scuro
    (80,  80, 255),    # 9  blu chiaro
    (0,  255,  80),    # 10 verde acceso
    (80, 255, 255),    # 11 ciano chiaro
    (255, 80,  80),    # 12 rosso chiaro
    (255, 80, 255),    # 13 magenta chiaro
    (255, 255, 80),    # 14 giallo
    (255, 255, 255),   # 15 bianco
]


# Palette CGA finale, quella che TITLEPIC.CCF può contenere.
# L'output DEVE usare solo questi indici 0..3.
CGA4 = [
    (0, 0, 0),          # 0 nero
    (0, 255, 255),      # 1 ciano/verde a video a seconda palette
    (255, 0, 255),      # 2 magenta
    (255, 255, 255),    # 3 bianco
]


def flat_palette(rgb_list):
    out = []
    for r, g, b in rgb_list:
        out.extend([r, g, b])
    out.extend([0] * (768 - len(out)))
    return out


def nearest_index(rgb, palette):
    r, g, b = rgb[:3]
    best_i = 0
    best_d = None

    for i, (pr, pg, pb) in enumerate(palette):
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if best_d is None or d < best_d:
            best_d = d
            best_i = i

    return best_i


def read_logical_indices(img, trust_indices=True):
    """
    Legge il PNG 160x200 e restituisce indici logici 0..15.
    """
    if img.size != (160, 200):
        raise ValueError(f"Dimensione errata: {img.size}. Atteso 160x200.")

    if img.mode == "P":
        data = list(img.getdata())

        if trust_indices and max(data) <= 15:
            return data, "uso diretto degli indici PNG 0..15"

        pal = img.getpalette()
        if not pal:
            raise ValueError("PNG palettizzato senza palette leggibile")

        result = []
        for idx in data:
            rgb = tuple(pal[idx * 3:idx * 3 + 3])
            result.append(nearest_index(rgb, DOS16))

        return result, "palette PNG rimappata su DOS16"

    rgb = img.convert("RGB")
    result = [nearest_index(px, DOS16) for px in rgb.getdata()]
    return result, "RGB rimappato su DOS16"


def encode_index_to_cga_pair(idx):
    """
    Questo è il punto fondamentale.

    Indice logico 0..15:
        idx = hi*4 + lo

    diventa due pixel CGA:
        primo  = hi
        secondo = lo

    Esempi:
        0  -> 0,0
        1  -> 0,1
        2  -> 0,2
        3  -> 0,3
        4  -> 1,0
        5  -> 1,1
        ...
        14 -> 3,2
        15 -> 3,3
    """
    idx &= 0x0F
    left = (idx >> 2) & 0x03
    right = idx & 0x03
    return left, right


def build_encoded_png(indices):
    """
    Da 160x200 a 320x200.

    Ogni pixel logico 0..15 diventa due pixel CGA 0..3.
    """
    out = Image.new("P", (320, 200))
    out.putpalette(flat_palette(CGA4))

    out_data = [0] * (320 * 200)

    for y in range(200):
        src_row = y * 160
        dst_row = y * 320

        for x in range(160):
            idx = indices[src_row + x]
            a, b = encode_index_to_cga_pair(idx)

            out_data[dst_row + x * 2] = a
            out_data[dst_row + x * 2 + 1] = b

    out.putdata(out_data)
    return out


def build_pc1_preview(indices):
    """
    Preview teorica 160x200: mostra gli indici logici 0..15.
    Serve solo per controllo a PC moderno.
    """
    img = Image.new("P", (160, 200))
    img.putpalette(flat_palette(DOS16))
    img.putdata([i & 0x0F for i in indices])
    return img


def main():
    ap = argparse.ArgumentParser(
        description="Converte PNG 160x200 a 16 colori logici in PNG 320x200 CGA-encoded per PC1."
    )

    ap.add_argument("input_png", help="PNG sorgente 160x200")
    ap.add_argument("output_png", help="PNG output 320x200 da importare in TITLEPIC.CCF")

    ap.add_argument(
        "--no-trust-indices",
        action="store_true",
        help="Non usare direttamente gli indici PNG; rimappa via RGB su DOS16."
    )

    ap.add_argument(
        "--preview",
        action="store_true",
        help="Salva anche una preview teorica 160x200 della palette logica."
    )

    args = ap.parse_args()

    inp = Path(args.input_png)
    outp = Path(args.output_png)

    if not inp.exists():
        print(f"ERRORE: file non trovato: {inp}")
        sys.exit(1)

    img = Image.open(inp)

    indices, mode_info = read_logical_indices(
        img,
        trust_indices=not args.no_trust_indices
    )

    used = sorted(set(indices))

    encoded = build_encoded_png(indices)
    encoded.save(outp)

    print(f"Input:             {inp}")
    print(f"Output:            {outp}")
    print(f"Dimensione input:  {img.size}")
    print(f"Dimensione output: {encoded.size}")
    print(f"Metodo lettura:    {mode_info}")
    print(f"Indici usati:      {used}")
    print()
    print("Output generato con soli indici CGA 0..3.")
    print("Questo file è quello da mettere in work_titlepic\\image\\TITLEPIC.png")

    if args.preview:
        preview_path = outp.with_suffix(".logical_preview.png")
        build_pc1_preview(indices).save(preview_path)
        print(f"Preview logica:    {preview_path}")


if __name__ == "__main__":
    main()