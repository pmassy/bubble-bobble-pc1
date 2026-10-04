from pathlib import Path
from PIL import Image
import argparse
import hashlib
import json
import shutil
import sys


CLEAR_CODE = 0x100
END_CODE = 0x101
FIRST_FREE = 0x102
MAX_BITS = 12


# Palette CGA di lavoro.
# Gli indici 0..3 sono la cosa importante.
CGA_PALETTE = [
    (0, 0, 0),        # 0 nero
    (0, 170, 170),    # 1 ciano
    (170, 0, 170),    # 2 magenta
    (255, 255, 255),  # 3 bianco
]


def sha1_of(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


# =============================================================================
# LZW DECOMPRESS
# =============================================================================

class BitReaderLSB:
    def __init__(self, data: bytes):
        self.data = data
        self.bitpos = 0

    def read(self, width: int):
        value = 0

        for i in range(width):
            bytepos = self.bitpos // 8
            bit = self.bitpos % 8

            if bytepos >= len(self.data):
                return None

            if self.data[bytepos] & (1 << bit):
                value |= 1 << i

            self.bitpos += 1

        return value


def decompress_bubble_lzw(data: bytes) -> bytes:
    br = BitReaderLSB(data)

    dictionary = {i: bytes([i]) for i in range(256)}
    next_code = FIRST_FREE
    code_bits = 9
    next_limit = 1 << code_bits

    out = bytearray()
    previous = None

    while True:
        code = br.read(code_bits)

        if code is None:
            raise ValueError("Fine stream inattesa prima del codice END")

        if code == CLEAR_CODE:
            dictionary = {i: bytes([i]) for i in range(256)}
            next_code = FIRST_FREE
            code_bits = 9
            next_limit = 1 << code_bits
            previous = None
            continue

        if code == END_CODE:
            break

        if previous is None:
            if code not in dictionary:
                raise ValueError(f"Primo codice non valido {code:04X}")

            entry = dictionary[code]
            out += entry
            previous = entry
            continue

        if code in dictionary:
            entry = dictionary[code]
        elif code == next_code:
            entry = previous + previous[:1]
        else:
            raise ValueError(
                f"Codice non valido {code:04X}, "
                f"next_code={next_code:04X}, code_bits={code_bits}"
            )

        out += entry

        if next_code < (1 << MAX_BITS):
            dictionary[next_code] = previous + entry[:1]
            next_code += 1

            if next_code >= next_limit and code_bits < MAX_BITS:
                code_bits += 1
                next_limit = 1 << code_bits

        previous = entry

    return bytes(out)


# =============================================================================
# CGA RAW -> PNG
# =============================================================================

def make_cga_palette():
    palette_flat = []

    for rgb in CGA_PALETTE:
        palette_flat.extend(rgb)

    while len(palette_flat) < 256 * 3:
        palette_flat.extend((0, 0, 0))

    return palette_flat


def cga_raw_to_png(raw: bytes, width: int = 320, height: int = 200) -> Image.Image:
    """
    CGA 320x200 2bpp lineare:
        1 byte = 4 pixel
        bits 7-6 = pixel 0
        bits 5-4 = pixel 1
        bits 3-2 = pixel 2
        bits 1-0 = pixel 3
    """

    needed = width * height // 4

    if len(raw) < needed:
        raise ValueError(
            f"Raw troppo corto: {len(raw)} byte, attesi almeno {needed}"
        )

    img = Image.new("P", (width, height))
    img.putpalette(make_cga_palette())

    pos = 0

    for y in range(height):
        for x in range(0, width, 4):
            b = raw[pos]
            pos += 1

            p0 = (b >> 6) & 0x03
            p1 = (b >> 4) & 0x03
            p2 = (b >> 2) & 0x03
            p3 = b & 0x03

            img.putpixel((x, y), p0)
            img.putpixel((x + 1, y), p1)
            img.putpixel((x + 2, y), p2)
            img.putpixel((x + 3, y), p3)

    return img


def cga_raw_to_pc1_pattern_preview(raw: bytes, width: int = 320, height: int = 200) -> Image.Image:
    """
    Preview sperimentale PC1/pattern.

    Non pretende di simulare perfettamente il PC1 reale.
    Serve solo a vedere la logica:
        2 pixel CGA -> 1 valore 0..15

    Output:
        160x200, palette 16 colori provvisoria.
    """

    needed = width * height // 4

    if len(raw) < needed:
        raise ValueError(
            f"Raw troppo corto: {len(raw)} byte, attesi almeno {needed}"
        )

    palette_16 = [
        (0, 0, 0),
        (0, 0, 170),
        (0, 170, 0),
        (0, 170, 170),
        (170, 0, 0),
        (170, 0, 170),
        (170, 85, 0),
        (170, 170, 170),
        (85, 85, 85),
        (85, 85, 255),
        (85, 255, 85),
        (85, 255, 85),
        (255, 85, 85),
        (255, 85, 255),
        (255, 255, 85),
        (255, 255, 255),
    ]

    palette_flat = []
    for rgb in palette_16:
        palette_flat.extend(rgb)

    while len(palette_flat) < 256 * 3:
        palette_flat.extend((0, 0, 0))

    img = Image.new("P", (width // 2, height))
    img.putpalette(palette_flat)

    pos = 0

    for y in range(height):
        out_x = 0

        for _ in range(width // 4):
            b = raw[pos]
            pos += 1

            p0 = (b >> 6) & 0x03
            p1 = (b >> 4) & 0x03
            p2 = (b >> 2) & 0x03
            p3 = b & 0x03

            c0 = (p0 << 2) | p1
            c1 = (p2 << 2) | p3

            img.putpixel((out_x, y), c0)
            img.putpixel((out_x + 1, y), c1)

            out_x += 2

    return img


# =============================================================================
# EXTRACT
# =============================================================================

def extract_static_ccf(
    input_ccf: Path,
    out_dir: Path,
    clean: bool,
    offset: int,
    width: int,
    height: int,
):
    if not input_ccf.exists():
        raise FileNotFoundError(f"File non trovato: {input_ccf}")

    if clean and out_dir.exists():
        shutil.rmtree(out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)

    source_dir = out_dir / "source"
    image_dir = out_dir / "image"

    source_dir.mkdir(exist_ok=True)
    image_dir.mkdir(exist_ok=True)

    compressed = input_ccf.read_bytes()

    if len(compressed) <= offset:
        raise ValueError(
            f"Offset {offset} oltre la dimensione del file {len(compressed)}"
        )

    header = compressed[:offset]
    stream = compressed[offset:]

    raw = decompress_bubble_lzw(stream)

    image_size = width * height // 4
    image_raw = raw[:image_size]
    tail = raw[image_size:]

    stem = input_ccf.stem.upper()

    original_copy = source_dir / f"{stem}.CCF.original"
    raw_copy = source_dir / f"{stem}.CCF.raw"
    image_raw_copy = source_dir / f"{stem}.image_{image_size}.raw"
    tail_copy = source_dir / f"{stem}.tail.bin"

    original_copy.write_bytes(compressed)
    raw_copy.write_bytes(raw)
    image_raw_copy.write_bytes(image_raw)
    tail_copy.write_bytes(tail)

    png = cga_raw_to_png(image_raw, width, height)
    png_path = image_dir / f"{stem}.png"
    png.save(png_path)

    pc1_preview = cga_raw_to_pc1_pattern_preview(image_raw, width, height)
    pc1_preview_path = image_dir / f"{stem}.pc1_pattern_preview.png"
    pc1_preview.save(pc1_preview_path)

    manifest = {
        "format": "Bubble Bobble DOS static CCF CGA export",
        "source_file": str(input_ccf),
        "source_copy": str(original_copy),
        "raw_file": str(raw_copy),
        "image_png": str(png_path),
        "pc1_pattern_preview_png": str(pc1_preview_path),
        "offset": offset,
        "header_hex": header.hex(" ").upper(),
        "compressed_size": len(compressed),
        "compressed_sha1": sha1_of(compressed),
        "raw_size": len(raw),
        "raw_sha1": sha1_of(raw),
        "image_width": width,
        "image_height": height,
        "image_format": "CGA 2bpp packed, 4 pixels per byte",
        "image_raw_size": len(image_raw),
        "tail_size": len(tail),
        "notes": [
            "Modificare image/<nome>.png mantenendo dimensione 320x200.",
            "Il PNG principale è CGA 2bpp: indici colore 0..3.",
            "La preview pc1_pattern_preview è solo indicativa e non simula perfettamente il PC1 reale.",
            "Il builder dovrà riconvertire il PNG in raw CGA 2bpp e ricomprimere il CCF."
        ],
    }

    with (out_dir / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Input CCF:             {input_ccf}")
    print(f"Output cartella:       {out_dir}")
    print()
    print(f"Offset LZW:            {offset}")
    print(f"Header:                {header.hex(' ').upper() if header else '(nessuno)'}")
    print(f"Dimensione CCF:        {len(compressed)} byte")
    print(f"SHA1 CCF:              {sha1_of(compressed)}")
    print()
    print(f"Dimensione RAW:        {len(raw)} byte")
    print(f"SHA1 RAW:              {sha1_of(raw)}")
    print(f"Image RAW:             {len(image_raw)} byte")
    print(f"Tail dopo immagine:    {len(tail)} byte")
    print()
    print(f"PNG CGA creato:        {png_path}")
    print(f"Preview PC1 creata:    {pc1_preview_path}")
    print(f"Manifest:              {out_dir / 'manifest.json'}")


def main():
    ap = argparse.ArgumentParser(
        description="Estrae una immagine statica CCF CGA di Bubble Bobble"
    )

    ap.add_argument(
        "input_ccf",
        help="File CCF da estrarre, es. TITLEPIC.CCF"
    )

    ap.add_argument(
        "--out",
        default=None,
        help="Cartella output. Default: work_<nomefile>"
    )

    ap.add_argument(
        "--clean",
        action="store_true",
        help="Cancella la cartella output prima di estrarre"
    )

    ap.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Offset inizio stream LZW. Per TITLEPIC.CCF usare 0. Default: 0"
    )

    ap.add_argument(
        "--width",
        type=int,
        default=320,
        help="Larghezza immagine. Default: 320"
    )

    ap.add_argument(
        "--height",
        type=int,
        default=200,
        help="Altezza immagine. Default: 200"
    )

    args = ap.parse_args()

    input_path = Path(args.input_ccf)

    if args.out:
        out_dir = Path(args.out)
    else:
        out_dir = Path(f"work_{input_path.stem.lower()}")

    try:
        extract_static_ccf(
            input_ccf=input_path,
            out_dir=out_dir,
            clean=args.clean,
            offset=args.offset,
            width=args.width,
            height=args.height,
        )
    except Exception as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()