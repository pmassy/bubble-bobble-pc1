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


CGA_PALETTE = [
    (0, 0, 0),        # 0 nero
    (0, 170, 170),    # 1 ciano
    (170, 0, 170),    # 2 magenta
    (255, 255, 255),  # 3 bianco
]


def sha1_of(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def u16le(data: bytes, off: int) -> int:
    return data[off] | (data[off + 1] << 8)


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
    """
    Decompressore LZW Bubble Bobble DOS.

    Codici:
        0x100 = CLEAR
        0x101 = END
        0x102 = primo codice libero

    Bitstream:
        LSB-first
        9..12 bit
    """
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
                raise ValueError(
                    f"Primo codice non valido {code:04X} alla posizione bit {br.bitpos}"
                )

            entry = dictionary[code]
            out += entry
            previous = entry
            continue

        if code in dictionary:
            entry = dictionary[code]
        elif code == next_code:
            # caso speciale LZW KwKwK
            entry = previous + previous[:1]
        else:
            raise ValueError(
                f"Codice non valido {code:04X} alla posizione bit {br.bitpos}, "
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


def scan_sprite_blocks(raw: bytes):
    """
    Formato raw sprite:
        uint16 length, incluso il word stesso
        payload
        ...
        uint16 0000 terminatore
        tail eventuale
    """
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

        payload = raw[off + 2:end]

        blocks.append({
            "index": index,
            "offset": off,
            "length": length,
            "payload": payload,
        })

        off = end
        index += 1


def make_palette_image(width: int, height: int) -> Image.Image:
    img = Image.new("P", (width, height))

    palette_flat = []
    for rgb in CGA_PALETTE:
        palette_flat.extend(rgb)

    while len(palette_flat) < 256 * 3:
        palette_flat.extend((0, 0, 0))

    img.putpalette(palette_flat)
    return img


def cga_bytes_to_png(data: bytes, width_bytes: int, height: int) -> Image.Image:
    """
    CGA 2bpp:
        1 byte = 4 pixel
        bits 7-6, 5-4, 3-2, 1-0
    """
    width_pixels = width_bytes * 4
    needed = width_bytes * height

    if len(data) < needed:
        raise ValueError("Dati immagine insufficienti")

    img = make_palette_image(width_pixels, height)

    pos = 0

    for y in range(height):
        for xb in range(width_bytes):
            b = data[pos]
            pos += 1

            pixels = [
                (b >> 6) & 0x03,
                (b >> 4) & 0x03,
                (b >> 2) & 0x03,
                b & 0x03,
            ]

            x = xb * 4

            for i, p in enumerate(pixels):
                img.putpixel((x + i, y), p)

    return img


def cga_mask_to_png(mask: bytes, width_bytes: int, height: int) -> Image.Image:
    """
    Export semplificato della maschera:

        pixel nero  = 0 = fondo preservato
        pixel bianco = 1 = zona sprite

    Nel file originale la mask è una AND mask:
        11b = lascia invariato
        altro = zona interessata dallo sprite
    """
    width_pixels = width_bytes * 4
    needed = width_bytes * height

    if len(mask) < needed:
        raise ValueError("Dati maschera insufficienti")

    img = Image.new("P", (width_pixels, height))

    palette_flat = [
        0, 0, 0,          # 0 nero
        255, 255, 255,    # 1 bianco
    ]

    while len(palette_flat) < 256 * 3:
        palette_flat.extend((0, 0, 0))

    img.putpalette(palette_flat)

    pos = 0

    for y in range(height):
        for xb in range(width_bytes):
            b = mask[pos]
            pos += 1

            parts = [
                (b >> 6) & 0x03,
                (b >> 4) & 0x03,
                (b >> 2) & 0x03,
                b & 0x03,
            ]

            x = xb * 4

            for i, m in enumerate(parts):
                value = 0 if m == 0x03 else 1
                img.putpixel((x + i, y), value)

    return img


def compose_cga(mask: bytes, image: bytes, width_bytes: int, height: int, bg_color: int = 3) -> Image.Image:
    """
    Crea preview composta:
        output = (background & mask) | image
    """
    size = width_bytes * height

    if len(mask) < size or len(image) < size:
        raise ValueError("Dati insufficienti per compositing")

    c = bg_color & 0x03
    bg_byte = (c << 6) | (c << 4) | (c << 2) | c

    out = bytearray(size)

    for i in range(size):
        out[i] = (bg_byte & mask[i]) | image[i]

    return cga_bytes_to_png(bytes(out), width_bytes, height)


def parse_sprite_block(block):
    payload = block["payload"]

    if len(payload) < 4:
        raise ValueError(f"Blocco {block['index']} troppo corto")

    width_bytes = payload[0]
    height = payload[1]
    flag = payload[2]
    align = payload[3]

    base = payload[4:]
    size = width_bytes * height

    phases = []

    for phase in range(8):
        p = phase * 4

        if p + 4 > len(base):
            break

        image_off = u16le(base, p)
        mask_off = u16le(base, p + 2)

        image_ok = image_off + size <= len(base)
        mask_ok = mask_off + size <= len(base)

        phases.append({
            "phase": phase,
            "image_offset": image_off,
            "mask_offset": mask_off,
            "image_offset_hex": f"{image_off:04X}",
            "mask_offset_hex": f"{mask_off:04X}",
            "size": size,
            "valid": image_ok and mask_ok,
        })

    return {
        "width_bytes": width_bytes,
        "width_pixels": width_bytes * 4,
        "height": height,
        "flag": flag,
        "align": align,
        "base": base,
        "phases": phases,
    }


def extract_sprites_ccf(
    input_ccf: Path,
    out_dir: Path,
    clean: bool,
    bg_color: int
):
    if not input_ccf.exists():
        raise FileNotFoundError(f"File non trovato: {input_ccf}")

    if clean and out_dir.exists():
        shutil.rmtree(out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)

    source_dir = out_dir / "source"
    sprites_dir = out_dir / "sprites"

    source_dir.mkdir(exist_ok=True)
    sprites_dir.mkdir(exist_ok=True)

    compressed = input_ccf.read_bytes()

    if len(compressed) < 2:
        raise ValueError("File CCF troppo corto")

    header = compressed[:2]
    compressed_stream = compressed[2:]

    raw = decompress_bubble_lzw(compressed_stream)

    original_copy = source_dir / "SPRITES.CCF.original"
    raw_copy = source_dir / "SPRITES.CCF.raw"

    original_copy.write_bytes(compressed)
    raw_copy.write_bytes(raw)

    blocks, terminator_offset, tail = scan_sprite_blocks(raw)

    manifest = {
        "format": "Bubble Bobble DOS SPRITES.CCF editable export",
        "source_file": str(input_ccf),
        "source_copy": str(original_copy),
        "raw_file": str(raw_copy),
        "header_hex": header.hex(" ").upper(),
        "compressed_size": len(compressed),
        "compressed_sha1": sha1_of(compressed),
        "raw_size": len(raw),
        "raw_sha1": sha1_of(raw),
        "block_count": len(blocks),
        "terminator_offset": terminator_offset,
        "terminator_offset_hex": f"{terminator_offset:06X}",
        "tail_length": len(tail),
        "sprites_folder": "sprites",
        "notes": [
            "Modificare solo i file phase_X_image.png, salvo diversa necessità.",
            "Non cambiare dimensioni, nomi file, info.json o manifest.json.",
            "Le phase possono condividere gli stessi dati fisici: il builder gestirà i duplicati.",
            "Le mask vengono esportate per ispezione; di default non saranno reimportate."
        ],
        "blocks": []
    }

    tail_path = source_dir / "_tail_after_terminator.bin"
    tail_path.write_bytes(tail)

    print(f"Input CCF:          {input_ccf}")
    print(f"Output cartella:    {out_dir}")
    print(f"Header:             {header.hex(' ').upper()}")
    print(f"Dimensione CCF:     {len(compressed)} byte")
    print(f"SHA1 CCF:           {sha1_of(compressed)}")
    print(f"Dimensione RAW:     {len(raw)} byte")
    print(f"SHA1 RAW:           {sha1_of(raw)}")
    print()
    print(f"Blocchi trovati:    {len(blocks)}")
    print(f"Terminatore:        {terminator_offset:06X}")
    print(f"Tail:               {len(tail)} byte")
    print()

    for block in blocks:
        parsed = parse_sprite_block(block)

        block_dir = sprites_dir / f"block_{block['index']:04d}"
        block_dir.mkdir(exist_ok=True)

        block_meta = {
            "index": block["index"],
            "offset": block["offset"],
            "offset_hex": f"{block['offset']:06X}",
            "length": block["length"],
            "length_hex": f"{block['length']:04X}",
            "payload_length": len(block["payload"]),
            "width_bytes": parsed["width_bytes"],
            "width_pixels": parsed["width_pixels"],
            "height": parsed["height"],
            "flag": parsed["flag"],
            "align": parsed["align"],
            "phases": parsed["phases"],
        }

        base = parsed["base"]
        size = parsed["width_bytes"] * parsed["height"]

        for ph in parsed["phases"]:
            if not ph["valid"]:
                continue

            phase = ph["phase"]
            image_off = ph["image_offset"]
            mask_off = ph["mask_offset"]

            image_data = base[image_off:image_off + size]
            mask_data = base[mask_off:mask_off + size]

            image_png = cga_bytes_to_png(
                image_data,
                parsed["width_bytes"],
                parsed["height"]
            )

            mask_png = cga_mask_to_png(
                mask_data,
                parsed["width_bytes"],
                parsed["height"]
            )

            composed_png = compose_cga(
                mask_data,
                image_data,
                parsed["width_bytes"],
                parsed["height"],
                bg_color=bg_color
            )

            image_png.save(block_dir / f"phase_{phase}_image.png")
            mask_png.save(block_dir / f"phase_{phase}_mask.png")
            composed_png.save(block_dir / f"phase_{phase}_composed.png")

        with (block_dir / "info.json").open("w", encoding="utf-8") as f:
            json.dump(block_meta, f, indent=2)

        manifest["blocks"].append({
            "index": block["index"],
            "folder": f"sprites/block_{block['index']:04d}",
            "offset_hex": block_meta["offset_hex"],
            "length_hex": block_meta["length_hex"],
            "payload_length": block_meta["payload_length"],
            "width_bytes": block_meta["width_bytes"],
            "width_pixels": block_meta["width_pixels"],
            "height": block_meta["height"],
            "flag": block_meta["flag"],
            "align": block_meta["align"],
        })

        print(
            f"block {block['index']:04d} "
            f"off={block['offset']:06X} "
            f"len={block['length']:04X} "
            f"size={parsed['width_pixels']}x{parsed['height']} "
            f"flag={parsed['flag']:02X} "
            f"align={parsed['align']:02X}"
        )

    with (out_dir / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print()
    print("Export completato.")
    print(f"Originale copiato:  {original_copy}")
    print(f"Raw salvato:        {raw_copy}")
    print(f"Sprites:            {sprites_dir}")
    print(f"Manifest:           {out_dir / 'manifest.json'}")


def main():
    ap = argparse.ArgumentParser(
        description="Estrae SPRITES.CCF Bubble Bobble in una cartella modificabile"
    )

    ap.add_argument(
        "input_ccf",
        help="File SPRITES.CCF originale"
    )

    ap.add_argument(
        "--out",
        default="work_ccf",
        help="Cartella di lavoro output. Default: work_ccf"
    )

    ap.add_argument(
        "--clean",
        action="store_true",
        help="Cancella la cartella output prima di esportare"
    )

    ap.add_argument(
        "--bg",
        type=int,
        default=3,
        help="Colore fondo per i composed PNG, 0..3. Default: 3"
    )

    args = ap.parse_args()

    try:
        extract_sprites_ccf(
            input_ccf=Path(args.input_ccf),
            out_dir=Path(args.out),
            clean=args.clean,
            bg_color=args.bg,
        )
    except Exception as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()