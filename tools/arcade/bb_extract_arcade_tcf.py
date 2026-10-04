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


# Palette provvisoria RGBI/EGA-like.
# Serve solo per editare in modo comodo.
# Gli indici 0..15 sono la cosa importante.
PALETTE_16 = [
    (0, 0, 0),          # 0 nero
    (0, 0, 170),        # 1 blu
    (0, 170, 0),        # 2 verde
    (0, 170, 170),      # 3 ciano
    (170, 0, 0),        # 4 rosso
    (170, 0, 170),      # 5 magenta
    (170, 85, 0),       # 6 marrone
    (170, 170, 170),    # 7 grigio chiaro
    (85, 85, 85),       # 8 grigio scuro
    (85, 85, 255),      # 9 blu chiaro
    (85, 255, 85),      # 10 verde chiaro
    (85, 255, 255),     # 11 ciano chiaro
    (255, 85, 85),      # 12 rosso chiaro
    (255, 85, 255),     # 13 magenta chiaro
    (255, 255, 85),     # 14 giallo
    (255, 255, 255),    # 15 bianco
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
                value |= (1 << i)

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


def raw_4bpp_to_png(raw: bytes, width: int = 320, height: int = 200) -> Image.Image:
    """
    Formato 4bpp packed:
        1 byte = 2 pixel
        nibble alto = pixel sinistro
        nibble basso = pixel destro
    """
    needed = width * height // 2

    if len(raw) < needed:
        raise ValueError(
            f"Raw troppo corto: {len(raw)} byte, attesi almeno {needed}"
        )

    img = Image.new("P", (width, height))

    palette_flat = []
    for rgb in PALETTE_16:
        palette_flat.extend(rgb)

    while len(palette_flat) < 256 * 3:
        palette_flat.extend((0, 0, 0))

    img.putpalette(palette_flat)

    pos = 0

    for y in range(height):
        for x in range(0, width, 2):
            b = raw[pos]
            pos += 1

            left = (b >> 4) & 0x0F
            right = b & 0x0F

            img.putpixel((x, y), left)
            img.putpixel((x + 1, y), right)

    return img


def extract_arcade_tcf(input_tcf: Path, out_dir: Path, clean: bool):
    if not input_tcf.exists():
        raise FileNotFoundError(f"File non trovato: {input_tcf}")

    if clean and out_dir.exists():
        shutil.rmtree(out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)

    source_dir = out_dir / "source"
    image_dir = out_dir / "image"

    source_dir.mkdir(exist_ok=True)
    image_dir.mkdir(exist_ok=True)

    compressed = input_tcf.read_bytes()

    if len(compressed) < 2:
        raise ValueError("File troppo corto")

    header = compressed[:2]
    stream = compressed[2:]

    raw = decompress_bubble_lzw(stream)

    image_size = 320 * 200 // 2  # 32000 byte
    image_raw = raw[:image_size]
    tail = raw[image_size:]

    original_copy = source_dir / "ARCADE.TCF.original"
    raw_copy = source_dir / "ARCADE.TCF.raw"
    image_raw_copy = source_dir / "ARCADE.image_32000.raw"
    tail_copy = source_dir / "ARCADE.tail.bin"

    original_copy.write_bytes(compressed)
    raw_copy.write_bytes(raw)
    image_raw_copy.write_bytes(image_raw)
    tail_copy.write_bytes(tail)

    png = raw_4bpp_to_png(image_raw, 320, 200)
    png_path = image_dir / "ARCADE.png"
    png.save(png_path)

    manifest = {
        "format": "Bubble Bobble DOS ARCADE.TCF static 4bpp export",
        "source_file": str(input_tcf),
        "source_copy": str(original_copy),
        "raw_file": str(raw_copy),
        "image_png": str(png_path),
        "header_hex": header.hex(" ").upper(),
        "compressed_size": len(compressed),
        "compressed_sha1": sha1_of(compressed),
        "raw_size": len(raw),
        "raw_sha1": sha1_of(raw),
        "image_width": 320,
        "image_height": 200,
        "image_format": "4bpp packed, high nibble left pixel, low nibble right pixel",
        "image_raw_size": len(image_raw),
        "tail_size": len(tail),
        "notes": [
            "Modificare image/ARCADE.png mantenendo dimensione 320x200.",
            "Gli indici colore 0..15 sono la parte importante.",
            "La palette PNG è solo una palette di lavoro.",
            "Il builder dovrà riconvertire ARCADE.png in raw 4bpp e ricomprimere ARCADE.TCF."
        ],
    }

    with (out_dir / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Input TCF:          {input_tcf}")
    print(f"Output cartella:    {out_dir}")
    print()
    print(f"Header:             {header.hex(' ').upper()}")
    print(f"Dimensione TCF:     {len(compressed)} byte")
    print(f"SHA1 TCF:           {sha1_of(compressed)}")
    print()
    print(f"Dimensione RAW:     {len(raw)} byte")
    print(f"SHA1 RAW:           {sha1_of(raw)}")
    print(f"Image RAW:          {len(image_raw)} byte")
    print(f"Tail dopo immagine: {len(tail)} byte")
    print()
    print(f"PNG creato:         {png_path}")
    print(f"Manifest:           {out_dir / 'manifest.json'}")


def main():
    ap = argparse.ArgumentParser(
        description="Estrae ARCADE.TCF Bubble Bobble in PNG 320x200 16 colori"
    )

    ap.add_argument(
        "input_tcf",
        help="File ARCADE.TCF"
    )

    ap.add_argument(
        "--out",
        default="work_arcade",
        help="Cartella output. Default: work_arcade"
    )

    ap.add_argument(
        "--clean",
        action="store_true",
        help="Cancella la cartella output prima di estrarre"
    )

    args = ap.parse_args()

    try:
        extract_arcade_tcf(
            input_tcf=Path(args.input_tcf),
            out_dir=Path(args.out),
            clean=args.clean,
        )
    except Exception as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()