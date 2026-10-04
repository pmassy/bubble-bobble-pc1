from pathlib import Path
from PIL import Image
import argparse
import hashlib
import json
import struct
import sys


CLEAR_CODE = 0x100
END_CODE = 0x101
FIRST_FREE = 0x102
MAX_BITS = 12


PALETTE_16 = [
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
    (85, 255, 255),
    (255, 85, 85),
    (255, 85, 255),
    (255, 255, 85),
    (255, 255, 255),
]


def sha1_of(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


# =============================================================================
# LZW DECOMPRESS - solo verifica
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
# LZW COMPRESS SAFE 9-BIT
# =============================================================================

class BitWriterLSB:
    def __init__(self):
        self.out = bytearray()
        self.bit_buffer = 0
        self.bit_count = 0

    def write(self, code: int, width: int):
        if code >= (1 << width):
            raise ValueError(f"Codice {code:04X} troppo grande per {width} bit")

        self.bit_buffer |= code << self.bit_count
        self.bit_count += width

        while self.bit_count >= 8:
            self.out.append(self.bit_buffer & 0xFF)
            self.bit_buffer >>= 8
            self.bit_count -= 8

    def finish(self) -> bytes:
        if self.bit_count > 0:
            self.out.append(self.bit_buffer & 0xFF)
            self.bit_buffer = 0
            self.bit_count = 0

        return bytes(self.out)


def reset_compress_dict():
    return {bytes([i]): i for i in range(256)}


def compress_chunk_9bit(data: bytes, bw: BitWriterLSB):
    if not data:
        return

    dictionary = reset_compress_dict()
    next_code = FIRST_FREE
    width = 9

    w = bytes([data[0]])

    for b in data[1:]:
        k = bytes([b])
        wk = w + k

        if wk in dictionary:
            w = wk
            continue

        bw.write(dictionary[w], width)

        if next_code < 0x1F0:
            dictionary[wk] = next_code
            next_code += 1

        w = k

    if w:
        bw.write(dictionary[w], width)


def lzw_compress_safe_9bit(data: bytes, chunk_size: int = 180) -> bytes:
    bw = BitWriterLSB()

    if len(data) == 0:
        bw.write(CLEAR_CODE, 9)
        bw.write(END_CODE, 9)
        return bw.finish()

    pos = 0

    while pos < len(data):
        chunk = data[pos:pos + chunk_size]

        bw.write(CLEAR_CODE, 9)
        compress_chunk_9bit(chunk, bw)

        pos += chunk_size

    bw.write(END_CODE, 9)

    return bw.finish()


# =============================================================================
# PNG 16 colori -> RAW 4bpp
# =============================================================================

def nearest_palette_index(rgb):
    r, g, b = rgb
    best_i = 0
    best_d = 10**12

    for i, (pr, pg, pb) in enumerate(PALETTE_16):
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < best_d:
            best_d = d
            best_i = i

    return best_i


def png_to_raw_4bpp(path: Path, width: int, height: int) -> bytes:
    img = Image.open(path)

    if img.size != (width, height):
        raise ValueError(
            f"{path}: dimensione errata {img.size}, attesa {(width, height)}"
        )

    if width % 2 != 0:
        raise ValueError("La larghezza deve essere pari")

    if img.mode == "P":
        pixels = list(img.getdata())

        for p in pixels:
            if p < 0 or p > 15:
                raise ValueError(f"{path}: indice colore fuori 0..15: {p}")
    else:
        img = img.convert("RGB")
        pixels = [nearest_palette_index(rgb) for rgb in img.getdata()]

    out = bytearray()

    pos = 0
    for y in range(height):
        for x in range(0, width, 2):
            left = pixels[pos] & 0x0F
            right = pixels[pos + 1] & 0x0F
            pos += 2

            out.append((left << 4) | right)

    return bytes(out)


def build_arcade_tcf(
    work_dir: Path,
    output_tcf: Path,
    output_raw: Path | None,
    chunk_size: int,
    verify: bool,
):
    manifest_path = work_dir / "manifest.json"
    source_dir = work_dir / "source"
    image_dir = work_dir / "image"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manca manifest.json: {manifest_path}")

    if not source_dir.exists():
        raise FileNotFoundError(f"Manca cartella source: {source_dir}")

    if not image_dir.exists():
        raise FileNotFoundError(f"Manca cartella image: {image_dir}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    original_tcf_path = source_dir / "ARCADE.TCF.original"
    original_raw_path = source_dir / "ARCADE.TCF.raw"
    image_png_path = image_dir / "ARCADE.png"

    if not original_tcf_path.exists():
        raise FileNotFoundError(f"Manca originale: {original_tcf_path}")

    if not original_raw_path.exists():
        raise FileNotFoundError(f"Manca raw originale: {original_raw_path}")

    if not image_png_path.exists():
        raise FileNotFoundError(f"Manca PNG: {image_png_path}")

    original_tcf = original_tcf_path.read_bytes()
    original_raw = original_raw_path.read_bytes()

    if len(original_tcf) < 2:
        raise ValueError("ARCADE.TCF.original troppo corto")

    header = original_tcf[:2]

    # Il TCF originale contiene un'immagine 320x200 4bpp.
    # Con la patch PC1 il renderer legge invece direttamente una sorgente
    # logica 160x200 4bpp: 2 pixel da 4 bit per byte = 80 byte per riga.
    original_width = int(manifest.get("image_width", 320))
    original_height = int(manifest.get("image_height", 200))
    original_image_size = original_width * original_height // 2

    target_width = 160
    target_height = 200
    target_image_size = target_width * target_height // 2

    if len(original_raw) < original_image_size:
        raise ValueError(
            f"Raw originale troppo corto: {len(original_raw)}, "
            f"attesi almeno {original_image_size}"
        )

    original_image_raw = original_raw[:original_image_size]
    tail = original_raw[original_image_size:]

    new_image_raw = png_to_raw_4bpp(
        image_png_path,
        target_width,
        target_height,
    )

    if len(new_image_raw) != target_image_size:
        raise ValueError(
            f"Raw immagine PC1 inatteso: {len(new_image_raw)}, "
            f"attesi {target_image_size}"
        )

    modified_raw = new_image_raw + tail

    if output_raw is None:
        output_raw = output_tcf.with_suffix(output_tcf.suffix + ".raw")

    output_tcf.parent.mkdir(parents=True, exist_ok=True)
    output_raw.parent.mkdir(parents=True, exist_ok=True)

    output_raw.write_bytes(modified_raw)

    compressed_stream = lzw_compress_safe_9bit(
        modified_raw,
        chunk_size=chunk_size
    )

    output_tcf_bytes = header + compressed_stream
    output_tcf.write_bytes(output_tcf_bytes)

    changed_bytes = sum(
        1 for a, b in zip(original_image_raw, new_image_raw)
        if a != b
    )

    print(f"Work dir:                  {work_dir}")
    print(f"Output TCF:                {output_tcf}")
    print(f"Output RAW:                {output_raw}")
    print()
    print(f"Header copiato:            {header.hex(' ').upper()}")
    print(f"Chunk size compressione:   {chunk_size}")
    print()
    print(f"Dimensione originale TCF:  {len(original_tcf)}")
    print(f"Dimensione nuovo TCF:      {len(output_tcf_bytes)}")
    print(f"SHA1 originale TCF:        {sha1_of(original_tcf)}")
    print(f"SHA1 nuovo TCF:            {sha1_of(output_tcf_bytes)}")
    print()
    print(f"Dimensione raw originale:  {len(original_raw)}")
    print(f"Dimensione raw modificato: {len(modified_raw)}")
    print(f"SHA1 raw originale:        {sha1_of(original_raw)}")
    print(f"SHA1 raw modificato:       {sha1_of(modified_raw)}")
    print()
    print(f"Immagine originale:        {original_width}x{original_height} ({original_image_size} byte)")
    print(f"Immagine PC1 nuova:         {target_width}x{target_height} ({target_image_size} byte)")
    print(f"Tail conservata:           {len(tail)} byte")
    print(f"Byte immagine cambiati:    {changed_bytes}")
    print()

    if verify:
        print("Verifica decompressione nuovo TCF...")

        check_raw = decompress_bubble_lzw(output_tcf_bytes[2:])

        if check_raw == modified_raw:
            print("VERIFICA: OK - il nuovo TCF decompresso coincide col raw modificato")
        else:
            print("VERIFICA: ERRORE - il nuovo TCF decompresso NON coincide col raw modificato")
            sys.exit(2)


def main():
    ap = argparse.ArgumentParser(
        description="Ricostruisce ARCADE.TCF PC1 160x200 16 colori da work_arcade/image/ARCADE.png"
    )

    ap.add_argument(
        "work_dir",
        help="Cartella creata da bb_extract_arcade_tcf.py, es. work_arcade"
    )

    ap.add_argument(
        "--out",
        default="build_arcade/ARCADE.TCF",
        help="File TCF da creare. Default: build_arcade/ARCADE.TCF"
    )

    ap.add_argument(
        "--raw-out",
        default=None,
        help="File raw da creare. Default: output + .raw"
    )

    ap.add_argument(
        "--chunk-size",
        type=int,
        default=180,
        help="Chunk size compressione LZW safe 9-bit. Default: 180"
    )

    ap.add_argument(
        "--no-verify",
        action="store_true",
        help="Disattiva verifica finale"
    )

    args = ap.parse_args()

    if args.chunk_size < 16 or args.chunk_size > 220:
        print("ERRORE: usa un chunk-size tra 16 e 220", file=sys.stderr)
        sys.exit(1)

    try:
        build_arcade_tcf(
            work_dir=Path(args.work_dir),
            output_tcf=Path(args.out),
            output_raw=Path(args.raw_out) if args.raw_out else None,
            chunk_size=args.chunk_size,
            verify=not args.no_verify,
        )
    except Exception as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()