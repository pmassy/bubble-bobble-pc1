from pathlib import Path
from PIL import Image
import argparse
import hashlib
import json
import sys


CLEAR_CODE = 0x100
END_CODE = 0x101
FIRST_FREE = 0x102


def sha1_of(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


# =============================================================================
# BIT WRITER LSB
# =============================================================================

class BitWriterLSB:
    def __init__(self):
        self.out = bytearray()
        self.bitbuf = 0
        self.bitcount = 0

    def write(self, value: int, width: int):
        self.bitbuf |= (value & ((1 << width) - 1)) << self.bitcount
        self.bitcount += width

        while self.bitcount >= 8:
            self.out.append(self.bitbuf & 0xFF)
            self.bitbuf >>= 8
            self.bitcount -= 8

    def finish(self) -> bytes:
        if self.bitcount:
            self.out.append(self.bitbuf & 0xFF)
            self.bitbuf = 0
            self.bitcount = 0

        return bytes(self.out)


# =============================================================================
# SAFE BUBBLE LZW COMPRESS
# =============================================================================
# Compressione volutamente prudente.
#
# Usa solo codici a 9 bit e inserisce CLEAR spesso.
# Il file compresso sarà più grande dell'originale, ma il loader di Bubble
# lo digerisce bene perché legge fino al codice END.
# =============================================================================

def compress_bubble_lzw_safe_9bit(data: bytes, chunk_size: int = 180) -> bytes:
    bw = BitWriterLSB()

    pos = 0

    while pos < len(data):
        chunk = data[pos:pos + chunk_size]
        pos += chunk_size

        bw.write(CLEAR_CODE, 9)

        dictionary = {bytes([i]): i for i in range(256)}
        next_code = FIRST_FREE

        if not chunk:
            continue

        w = bytes([chunk[0]])

        for b in chunk[1:]:
            c = bytes([b])
            wc = w + c

            if wc in dictionary:
                w = wc
            else:
                bw.write(dictionary[w], 9)

                if next_code < 512:
                    dictionary[wc] = next_code
                    next_code += 1
                else:
                    bw.write(CLEAR_CODE, 9)
                    dictionary = {bytes([i]): i for i in range(256)}
                    next_code = FIRST_FREE

                w = c

        if w:
            bw.write(dictionary[w], 9)

    bw.write(END_CODE, 9)

    return bw.finish()


# =============================================================================
# BUBBLE LZW DECOMPRESS, usato solo per verifica
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

        if next_code < 4096:
            dictionary[next_code] = previous + entry[:1]
            next_code += 1

            if next_code >= next_limit and code_bits < 12:
                code_bits += 1
                next_limit = 1 << code_bits

        previous = entry

    return bytes(out)


# =============================================================================
# PNG -> CGA RAW
# =============================================================================

def image_to_cga_raw(img: Image.Image, width: int = 320, height: int = 200) -> bytes:
    """
    Converte PNG 320x200 indicizzato o RGB in CGA packed 2bpp.

    Ogni byte contiene 4 pixel:
        bits 7-6 = pixel 0
        bits 5-4 = pixel 1
        bits 3-2 = pixel 2
        bits 1-0 = pixel 3

    I valori validi sono 0..3.

    Se l'immagine è P, usa direttamente gli indici palette.
    Se è RGB/RGBA, riduce al colore CGA più vicino tra:
        0 nero
        1 ciano
        2 magenta
        3 bianco
    """

    if img.size != (width, height):
        raise ValueError(
            f"Dimensione immagine errata: {img.size}, attesa {(width, height)}"
        )

    raw = bytearray()

    if img.mode == "P":
        for y in range(height):
            for x in range(0, width, 4):
                p0 = img.getpixel((x, y)) & 0x03
                p1 = img.getpixel((x + 1, y)) & 0x03
                p2 = img.getpixel((x + 2, y)) & 0x03
                p3 = img.getpixel((x + 3, y)) & 0x03

                b = (p0 << 6) | (p1 << 4) | (p2 << 2) | p3
                raw.append(b)

        return bytes(raw)

    # fallback RGB/RGBA
    img_rgb = img.convert("RGB")

    cga = [
        (0, 0, 0),        # 0 nero
        (0, 170, 170),    # 1 ciano
        (170, 0, 170),    # 2 magenta
        (255, 255, 255),  # 3 bianco
    ]

    def nearest_cga_index(rgb):
        r, g, b = rgb
        best_i = 0
        best_d = None

        for i, (cr, cg, cb) in enumerate(cga):
            d = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2

            if best_d is None or d < best_d:
                best_d = d
                best_i = i

        return best_i

    for y in range(height):
        for x in range(0, width, 4):
            p0 = nearest_cga_index(img_rgb.getpixel((x, y)))
            p1 = nearest_cga_index(img_rgb.getpixel((x + 1, y)))
            p2 = nearest_cga_index(img_rgb.getpixel((x + 2, y)))
            p3 = nearest_cga_index(img_rgb.getpixel((x + 3, y)))

            b = (p0 << 6) | (p1 << 4) | (p2 << 2) | p3
            raw.append(b)

    return bytes(raw)


# =============================================================================
# PC1 PREVIEW, uguale alla logica dello script estrattore
# =============================================================================

def make_pc1_pattern_preview(raw: bytes, width: int = 320, height: int = 200) -> Image.Image:
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
# BUILD
# =============================================================================

def build_static_ccf(work_dir: Path, out_file: Path, chunk_size: int):
    manifest_path = work_dir / "manifest.json"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest non trovato: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    width = int(manifest["image_width"])
    height = int(manifest["image_height"])
    offset = int(manifest["offset"])

    source_copy = Path(manifest["source_copy"])
    raw_file = Path(manifest["raw_file"])
    image_png = Path(manifest["image_png"])

    if not source_copy.exists():
        raise FileNotFoundError(f"File originale non trovato: {source_copy}")

    if not raw_file.exists():
        raise FileNotFoundError(f"Raw originale non trovato: {raw_file}")

    if not image_png.exists():
        raise FileNotFoundError(f"PNG modificato non trovato: {image_png}")

    original_compressed = source_copy.read_bytes()
    original_raw = raw_file.read_bytes()

    image_size = width * height // 4

    if len(original_raw) < image_size:
        raise ValueError(
            f"Raw originale troppo corto: {len(original_raw)}, attesi almeno {image_size}"
        )

    original_tail = original_raw[image_size:]

    img = Image.open(image_png)

    new_image_raw = image_to_cga_raw(img, width, height)
    new_raw = new_image_raw + original_tail

    compressed_stream = compress_bubble_lzw_safe_9bit(new_raw, chunk_size=chunk_size)

    header = original_compressed[:offset]
    new_ccf = header + compressed_stream

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(new_ccf)

    # Verifica decompressione
    verify_raw = decompress_bubble_lzw(new_ccf[offset:])

    if verify_raw != new_raw:
        raise ValueError("Verifica fallita: il file ricompresso non torna al raw modificato")

    # Salva anche raw e preview per controllo
    debug_raw = out_file.with_suffix(".raw")
    debug_preview = out_file.with_suffix(".pc1_pattern_preview.png")

    debug_raw.write_bytes(new_raw)
    make_pc1_pattern_preview(new_image_raw, width, height).save(debug_preview)

    print(f"Work dir:                 {work_dir}")
    print(f"PNG usato:                {image_png}")
    print()
    print(f"Raw originale:            {len(original_raw)} byte")
    print(f"Raw nuovo:                {len(new_raw)} byte")
    print(f"Tail preservata:          {len(original_tail)} byte")
    print()
    print(f"CCF originale:            {len(original_compressed)} byte")
    print(f"CCF nuovo:                {len(new_ccf)} byte")
    print(f"Chunk LZW safe:           {chunk_size}")
    print()
    print(f"SHA1 raw nuovo:           {sha1_of(new_raw)}")
    print(f"SHA1 ccf nuovo:           {sha1_of(new_ccf)}")
    print()
    print(f"Creato:                   {out_file}")
    print(f"Raw verifica:             {debug_raw}")
    print(f"Preview PC1 aggiornata:   {debug_preview}")
    print()
    print("Verifica decompressione:  OK")


def main():
    ap = argparse.ArgumentParser(
        description="Ricostruisce una immagine statica CCF CGA di Bubble Bobble"
    )

    ap.add_argument(
        "work_dir",
        help="Cartella di lavoro creata dall'estrattore, es. work_titlepic"
    )

    ap.add_argument(
        "--out",
        required=True,
        help="File CCF da generare, es. build_titlepic\\TITLEPIC.CCF"
    )

    ap.add_argument(
        "--chunk-size",
        type=int,
        default=180,
        help="Chunk size per compressione safe 9-bit. Default: 180"
    )

    args = ap.parse_args()

    try:
        build_static_ccf(
            work_dir=Path(args.work_dir),
            out_file=Path(args.out),
            chunk_size=args.chunk_size,
        )
    except Exception as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()