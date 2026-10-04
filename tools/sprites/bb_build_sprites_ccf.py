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


def sha1_of(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def u16le(data: bytes, off: int) -> int:
    return data[off] | (data[off + 1] << 8)


# =============================================================================
# LZW DECOMPRESS - usato solo per verifica finale
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
    """
    Comprime un blocco piccolo usando solo codici a 9 bit.
    Non scrive CLEAR iniziale né END finale.
    """
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

        # Restiamo sotto il cambio 9->10 bit.
        if next_code < 0x1F0:
            dictionary[wk] = next_code
            next_code += 1

        w = k

    if w:
        bw.write(dictionary[w], width)


def lzw_compress_safe_9bit(data: bytes, chunk_size: int = 180) -> bytes:
    """
    Compressore prudente:
    CLEAR + chunk 9-bit + CLEAR + chunk 9-bit ... + END

    File meno compresso, ma compatibile col decompressore del gioco.
    """
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
# RAW BLOCKS
# =============================================================================

def scan_sprite_blocks(raw: bytes):
    blocks = []
    off = 0
    index = 0

    while True:
        if off + 2 > len(raw):
            raise ValueError(f"Fine file inattesa a offset {off:06X}")

        length = u16le(raw, off)

        if length == 0:
            terminator_offset = off
            tail = raw[off + 2:]
            return blocks, terminator_offset, tail

        if length < 2:
            raise ValueError(
                f"Lunghezza blocco non valida: idx={index}, off={off:06X}, len={length:04X}"
            )

        end = off + length

        if end > len(raw):
            raise ValueError(
                f"Blocco oltre EOF: idx={index}, off={off:06X}, len={length:04X}, end={end:06X}"
            )

        payload = bytearray(raw[off + 2:end])

        blocks.append({
            "index": index,
            "offset": off,
            "length": length,
            "payload": payload,
        })

        off = end
        index += 1


def rebuild_raw(blocks, tail: bytes) -> bytes:
    out = bytearray()

    for block in blocks:
        payload = bytes(block["payload"])
        length = len(payload) + 2
        out += struct.pack("<H", length)
        out += payload

    out += b"\x00\x00"
    out += tail

    return bytes(out)


# =============================================================================
# PNG -> CGA BYTES
# =============================================================================

def png_to_cga_bytes(path: Path, width_pixels: int, height: int) -> bytes:
    """
    Converte PNG in byte CGA 2bpp.

    CGA:
        1 byte = 4 pixel
        pixel 0 -> bits 7-6
        pixel 1 -> bits 5-4
        pixel 2 -> bits 3-2
        pixel 3 -> bits 1-0
    """
    img = Image.open(path)

    if img.size != (width_pixels, height):
        raise ValueError(
            f"{path}: dimensione errata {img.size}, attesa {(width_pixels, height)}"
        )

    if width_pixels % 4 != 0:
        raise ValueError(f"{path}: width_pixels non multiplo di 4")

    width_bytes = width_pixels // 4

    if img.mode == "P":
        pixels = list(img.getdata())

        for p in pixels:
            if p not in (0, 1, 2, 3):
                raise ValueError(f"{path}: trovato indice colore non CGA: {p}")

    else:
        img = img.convert("RGB")

        cga_palette = [
            (0, 0, 0),
            (0, 170, 170),
            (170, 0, 170),
            (255, 255, 255),
        ]

        def nearest_cga(rgb):
            r, g, b = rgb
            best_i = 0
            best_d = 10**12

            for i, (pr, pg, pb) in enumerate(cga_palette):
                d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
                if d < best_d:
                    best_d = d
                    best_i = i

            return best_i

        pixels = [nearest_cga(rgb) for rgb in img.getdata()]

    out = bytearray()

    pos = 0
    for y in range(height):
        for xb in range(width_bytes):
            p0 = pixels[pos] & 0x03
            p1 = pixels[pos + 1] & 0x03
            p2 = pixels[pos + 2] & 0x03
            p3 = pixels[pos + 3] & 0x03
            pos += 4

            b = (p0 << 6) | (p1 << 4) | (p2 << 2) | p3
            out.append(b)

    return bytes(out)


def mask_png_to_cga_mask_bytes(path: Path, width_pixels: int, height: int) -> bytes:
    """
    Converte phase_X_mask.png in maschera AND CGA.

    Export:
        0 = nero   = fondo preservato
        1 = bianco = zona sprite

    Reimport:
        0 -> 11b
        1 -> 00b

    Di default lo script non importa le mask.
    """
    img = Image.open(path)

    if img.size != (width_pixels, height):
        raise ValueError(
            f"{path}: dimensione errata {img.size}, attesa {(width_pixels, height)}"
        )

    if width_pixels % 4 != 0:
        raise ValueError(f"{path}: width_pixels non multiplo di 4")

    width_bytes = width_pixels // 4

    if img.mode == "P":
        pixels = list(img.getdata())
    else:
        img = img.convert("L")
        pixels = [1 if v >= 128 else 0 for v in img.getdata()]

    out = bytearray()

    pos = 0
    for y in range(height):
        for xb in range(width_bytes):
            parts = []

            for _ in range(4):
                v = pixels[pos]
                pos += 1

                parts.append(0x03 if v == 0 else 0x00)

            b = (parts[0] << 6) | (parts[1] << 4) | (parts[2] << 2) | parts[3]
            out.append(b)

    return bytes(out)


# =============================================================================
# BUILD
# =============================================================================

def build_sprites_ccf(
    work_dir: Path,
    output_ccf: Path,
    output_raw: Path | None,
    chunk_size: int,
    import_masks: bool,
    verify: bool,
):
    manifest_path = work_dir / "manifest.json"
    source_dir = work_dir / "source"
    sprites_dir = work_dir / "sprites"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manca manifest.json: {manifest_path}")

    if not source_dir.exists():
        raise FileNotFoundError(f"Manca cartella source: {source_dir}")

    if not sprites_dir.exists():
        raise FileNotFoundError(f"Manca cartella sprites: {sprites_dir}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    original_ccf_path = source_dir / "SPRITES.CCF.original"
    original_raw_path = source_dir / "SPRITES.CCF.raw"

    if not original_ccf_path.exists():
        raise FileNotFoundError(f"Manca originale compresso: {original_ccf_path}")

    if not original_raw_path.exists():
        raise FileNotFoundError(f"Manca raw originale: {original_raw_path}")

    original_ccf = original_ccf_path.read_bytes()
    original_raw = original_raw_path.read_bytes()

    if len(original_ccf) < 2:
        raise ValueError("SPRITES.CCF.original troppo corto")

    header = original_ccf[:2]

    blocks, terminator_offset, tail = scan_sprite_blocks(original_raw)

    expected_blocks = manifest.get("block_count")
    if expected_blocks is not None and expected_blocks != len(blocks):
        raise ValueError(
            f"Numero blocchi diverso: manifest={expected_blocks}, raw={len(blocks)}"
        )

    changed_images = 0
    changed_masks = 0
    written_images = 0
    written_masks = 0
    skipped_duplicate_images = 0
    skipped_duplicate_masks = 0

    for block in blocks:
        idx = block["index"]
        block_dir = sprites_dir / f"block_{idx:04d}"
        info_path = block_dir / "info.json"

        if not block_dir.exists():
            raise FileNotFoundError(f"Manca cartella blocco: {block_dir}")

        if not info_path.exists():
            raise FileNotFoundError(f"Manca info.json per blocco {idx}: {info_path}")

        info = json.loads(info_path.read_text(encoding="utf-8"))

        width_pixels = info["width_pixels"]
        width_bytes = info["width_bytes"]
        height = info["height"]
        size = width_bytes * height

        payload = block["payload"]
        base_start = 4

        if len(payload) < base_start:
            raise ValueError(f"Blocco {idx}: payload troppo corto")

        base_len = len(payload) - base_start

        written_image_ranges_for_block = set()
        written_mask_ranges_for_block = set()

        for ph in info["phases"]:
            if not ph.get("valid", False):
                continue

            phase = ph["phase"]
            image_off = ph["image_offset"]
            mask_off = ph["mask_offset"]

            if image_off + size > base_len:
                raise ValueError(f"Blocco {idx} phase {phase}: image fuori range")

            if mask_off + size > base_len:
                raise ValueError(f"Blocco {idx} phase {phase}: mask fuori range")

            image_png = block_dir / f"phase_{phase}_image.png"
            mask_png = block_dir / f"phase_{phase}_mask.png"

            if not image_png.exists():
                raise FileNotFoundError(f"Manca image PNG: {image_png}")

            image_range = (
                base_start + image_off,
                base_start + image_off + size
            )

            if image_range in written_image_ranges_for_block:
                skipped_duplicate_images += 1
            else:
                image_bytes = png_to_cga_bytes(image_png, width_pixels, height)

                old_image = bytes(payload[image_range[0]:image_range[1]])

                if image_bytes != old_image:
                    changed_images += 1

                payload[image_range[0]:image_range[1]] = image_bytes
                written_images += 1
                written_image_ranges_for_block.add(image_range)

            if import_masks:
                if not mask_png.exists():
                    raise FileNotFoundError(f"Manca mask PNG: {mask_png}")

                mask_range = (
                    base_start + mask_off,
                    base_start + mask_off + size
                )

                if mask_range in written_mask_ranges_for_block:
                    skipped_duplicate_masks += 1
                else:
                    mask_bytes = mask_png_to_cga_mask_bytes(
                        mask_png,
                        width_pixels,
                        height
                    )

                    old_mask = bytes(payload[mask_range[0]:mask_range[1]])

                    if mask_bytes != old_mask:
                        changed_masks += 1

                    payload[mask_range[0]:mask_range[1]] = mask_bytes
                    written_masks += 1
                    written_mask_ranges_for_block.add(mask_range)

    modified_raw = rebuild_raw(blocks, tail)

    output_ccf.parent.mkdir(parents=True, exist_ok=True)

    if output_raw is None:
        output_raw = output_ccf.with_suffix(output_ccf.suffix + ".raw")

    output_raw.parent.mkdir(parents=True, exist_ok=True)

    output_raw.write_bytes(modified_raw)

    compressed_stream = lzw_compress_safe_9bit(
        modified_raw,
        chunk_size=chunk_size
    )

    output_ccf_bytes = header + compressed_stream
    output_ccf.write_bytes(output_ccf_bytes)

    print(f"Work dir:                  {work_dir}")
    print(f"Output CCF:                {output_ccf}")
    print(f"Output RAW:                {output_raw}")
    print()
    print(f"Header copiato:            {header.hex(' ').upper()}")
    print(f"Chunk size compressione:   {chunk_size}")
    print()
    print(f"Raw originale size:        {len(original_raw)}")
    print(f"Raw modificato size:       {len(modified_raw)}")
    print(f"Raw originale SHA1:        {sha1_of(original_raw)}")
    print(f"Raw modificato SHA1:       {sha1_of(modified_raw)}")
    print()
    print(f"CCF originale size:        {len(original_ccf)}")
    print(f"CCF nuovo size:            {len(output_ccf_bytes)}")
    print(f"CCF originale SHA1:        {sha1_of(original_ccf)}")
    print(f"CCF nuovo SHA1:            {sha1_of(output_ccf_bytes)}")
    print()
    print(f"Blocchi:                   {len(blocks)}")
    print(f"Terminatore:               {terminator_offset:06X}")
    print(f"Tail conservata:           {len(tail)} byte")
    print()
    print(f"Image scritte:             {written_images}")
    print(f"Image cambiate:            {changed_images}")
    print(f"Image duplicate saltate:   {skipped_duplicate_images}")
    print(f"Mask scritte:              {written_masks}")
    print(f"Mask cambiate:             {changed_masks}")
    print(f"Mask duplicate saltate:    {skipped_duplicate_masks}")
    print()

    if verify:
        print("Verifica decompressione nuovo CCF...")

        decompressed_check = decompress_bubble_lzw(output_ccf_bytes[2:])

        if decompressed_check == modified_raw:
            print("VERIFICA: OK - il nuovo CCF decompresso coincide col raw modificato")
        else:
            print("VERIFICA: ERRORE - il nuovo CCF decompresso NON coincide col raw modificato")

            min_len = min(len(decompressed_check), len(modified_raw))
            first_diff = None

            for i in range(min_len):
                if decompressed_check[i] != modified_raw[i]:
                    first_diff = i
                    break

            if first_diff is not None:
                print(
                    f"Prima differenza a offset {first_diff:06X}: "
                    f"raw={modified_raw[first_diff]:02X} "
                    f"decomp={decompressed_check[first_diff]:02X}"
                )
            elif len(decompressed_check) != len(modified_raw):
                print(
                    "I dati coincidono fino alla fine del più corto, "
                    "ma hanno lunghezze diverse."
                )

            sys.exit(2)


def main():
    ap = argparse.ArgumentParser(
        description="Ricostruisce SPRITES.CCF da una cartella work_ccf modificata"
    )

    ap.add_argument(
        "work_dir",
        help="Cartella di lavoro creata da bb_extract_sprites_ccf.py, es. work_ccf"
    )

    ap.add_argument(
        "--out",
        default="build/SPRITES.CCF",
        help="File CCF da creare. Default: build/SPRITES.CCF"
    )

    ap.add_argument(
        "--raw-out",
        default=None,
        help="File raw modificato da creare. Default: stesso nome dell'output + .raw"
    )

    ap.add_argument(
        "--chunk-size",
        type=int,
        default=180,
        help="Chunk size compressione LZW safe 9-bit. Default: 180"
    )

    ap.add_argument(
        "--import-masks",
        action="store_true",
        help="Importa anche phase_X_mask.png. Default: importa solo phase_X_image.png"
    )

    ap.add_argument(
        "--no-verify",
        action="store_true",
        help="Disattiva verifica finale di decompressione"
    )

    args = ap.parse_args()

    if args.chunk_size < 16 or args.chunk_size > 220:
        print("ERRORE: usa un chunk-size tra 16 e 220", file=sys.stderr)
        sys.exit(1)

    try:
        build_sprites_ccf(
            work_dir=Path(args.work_dir),
            output_ccf=Path(args.out),
            output_raw=Path(args.raw_out) if args.raw_out else None,
            chunk_size=args.chunk_size,
            import_masks=args.import_masks,
            verify=not args.no_verify,
        )
    except Exception as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()