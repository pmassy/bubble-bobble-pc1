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


# Palette 16 colori di lavoro.
# Gli indici 0..15 sono la cosa più importante.
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


def sha1_of(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


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
            raise ValueError("Fine stream inattesa prima di END")

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
                raise ValueError(f"Primo codice non valido: {code:04X}")

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
                f"next_code={next_code:04X}, bits={code_bits}"
            )

        out += entry

        if next_code < (1 << MAX_BITS):
            dictionary[next_code] = previous + entry[:1]
            next_code += 1

            if next_code >= next_limit and code_bits < MAX_BITS:
                code_bits += 1
                next_limit <<= 1

        previous = entry

    return bytes(out)


def make_palette():
    flat = []

    for rgb in PALETTE16:
        flat.extend(rgb)

    while len(flat) < 256 * 3:
        flat.extend((0, 0, 0))

    return flat


def raw4bpp_to_png(raw: bytes, width=320, height=200) -> Image.Image:
    needed = width * height // 2

    if len(raw) < needed:
        raise ValueError(
            f"Raw troppo corto: {len(raw)} byte, attesi almeno {needed}"
        )

    img = Image.new("P", (width, height))
    img.putpalette(make_palette())

    data = []

    pos = 0
    for _y in range(height):
        for _x in range(0, width, 2):
            b = raw[pos]
            pos += 1

            left = (b >> 4) & 0x0F
            right = b & 0x0F

            data.append(left)
            data.append(right)

    img.putdata(data)
    return img


def extract(input_tcf: Path, out_dir: Path, clean: bool, offset: int):
    if not input_tcf.exists():
        raise FileNotFoundError(f"File non trovato: {input_tcf}")

    if clean and out_dir.exists():
        shutil.rmtree(out_dir)

    source_dir = out_dir / "source"
    image_dir = out_dir / "image"

    source_dir.mkdir(parents=True, exist_ok=True)
    image_dir.mkdir(parents=True, exist_ok=True)

    comp = input_tcf.read_bytes()

    if offset < 0 or offset > len(comp):
        raise ValueError("Offset non valido")

    header = comp[:offset]
    raw = decompress_bubble_lzw(comp[offset:])

    image_size = 32000

    if len(raw) < image_size:
        raise ValueError(
            f"Decompressione troppo corta: {len(raw)} byte"
        )

    image_raw = raw[:image_size]
    tail = raw[image_size:]

    original_copy = source_dir / "BBLOCKS.TCF.original"
    raw_copy = source_dir / "BBLOCKS.TCF.raw"
    image_raw_copy = source_dir / "BBLOCKS.image_32000.raw"
    tail_copy = source_dir / "BBLOCKS.tail.bin"

    original_copy.write_bytes(comp)
    raw_copy.write_bytes(raw)
    image_raw_copy.write_bytes(image_raw)
    tail_copy.write_bytes(tail)

    png = raw4bpp_to_png(image_raw)
    png_path = image_dir / "BBLOCKS.png"
    png.save(png_path)

    manifest = {
        "source_file": str(input_tcf),
        "offset": offset,
        "header_hex": header.hex(" ").upper(),
        "compressed_size": len(comp),
        "compressed_sha1": sha1_of(comp),
        "raw_size": len(raw),
        "raw_sha1": sha1_of(raw),
        "image_raw_size": len(image_raw),
        "tail_size": len(tail),
        "image_width": 320,
        "image_height": 200,
        "image_format": "4bpp packed, high nibble = left pixel, low nibble = right pixel",
        "image_png": str(png_path),
    }

    with (out_dir / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Input:              {input_tcf}")
    print(f"Output dir:         {out_dir}")
    print(f"Offset LZW:         {offset}")
    print(f"Raw decompressi:    {len(raw)} byte")
    print(f"Immagine:           {len(image_raw)} byte")
    print(f"Tail:               {len(tail)} byte")
    print(f"PNG:                {png_path}")
    print(f"Indici palette:     0..15")
    print(f"Formato:            320x200, 4bpp")


def main():
    ap = argparse.ArgumentParser(
        description="Estrae BBLOCKS.TCF in PNG palettizzato 16 colori."
    )

    ap.add_argument(
        "input_tcf",
        help="BBLOCKS.TCF"
    )

    ap.add_argument(
        "--out",
        default="work_bblocks_tcf",
        help="Cartella output"
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
        help="Offset stream LZW. Per BBLOCKS.TCF usare 0."
    )

    args = ap.parse_args()

    try:
        extract(
            Path(args.input_tcf),
            Path(args.out),
            args.clean,
            args.offset,
        )
    except Exception as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()