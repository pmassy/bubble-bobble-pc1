from pathlib import Path
from PIL import Image
import argparse
import sys

CLEAR = 0x100
END   = 0x101
FIRST = 0x102


def read_indices_160(path: Path):
    img = Image.open(path)

    if img.size != (160, 200):
        raise ValueError(f"{path}: dimensioni {img.size}, attese 160x200")

    if img.mode != "P":
        raise ValueError(
            f"{path}: il PNG deve essere indicizzato (mode P), trovato {img.mode}"
        )

    # Compatibile con Pillow attuale e futuro.
    try:
        pixels = list(img.get_flattened_data())
    except AttributeError:
        pixels = list(img.getdata())

    used = sorted(set(pixels))
    bad = [v for v in used if not 0 <= v <= 15]
    if bad:
        raise ValueError(f"Indici fuori range 0..15: {bad}")

    return img, pixels, used


def encode_pc1_to_cga_raw(pixels):
    """
    160x200 logical 16-color -> 320x200 CGA-coded, packed 2bpp.

    Per ogni pixel logico i:
        left  = (i >> 2) & 3
        right = i & 3

    Quindi ogni pixel logico diventa due pixel fisici CGA.
    Quattro pixel CGA vengono poi impacchettati in un byte:
        bits 7-6, 5-4, 3-2, 1-0
    """
    raw = bytearray()

    for y in range(200):
        row = pixels[y * 160:(y + 1) * 160]
        cga = []

        for idx in row:
            cga.append((idx >> 2) & 3)
            cga.append(idx & 3)

        # 320 pixel / 4 = 80 byte per riga
        for x in range(0, 320, 4):
            p0, p1, p2, p3 = cga[x:x+4]
            b = (p0 << 6) | (p1 << 4) | (p2 << 2) | p3
            raw.append(b)

    if len(raw) != 16000:
        raise AssertionError(f"Raw inatteso: {len(raw)} byte")

    return bytes(raw)


def lzw_codes_for_chunk(data: bytes):
    """
    Genera codici LZW standard per un singolo chunk, partendo da dizionario pulito.
    Il chunk e' volutamente corto per restare sempre a 9 bit.
    """
    if not data:
        return []

    dictionary = {bytes([i]): i for i in range(256)}
    next_code = FIRST

    w = bytes([data[0]])
    out = []

    for b in data[1:]:
        c = bytes([b])
        wc = w + c

        if wc in dictionary:
            w = wc
        else:
            out.append(dictionary[w])

            if next_code < 0x200:   # restiamo volontariamente a 9 bit
                dictionary[wc] = next_code
                next_code += 1

            w = c

    out.append(dictionary[w])
    return out


def pack_9bit_lsb(codes):
    out = bytearray()
    bitbuf = 0
    nbits = 0

    for code in codes:
        if not 0 <= code <= 0x1FF:
            raise ValueError(f"Codice non 9-bit: {code:04X}")

        bitbuf |= code << nbits
        nbits += 9

        while nbits >= 8:
            out.append(bitbuf & 0xFF)
            bitbuf >>= 8
            nbits -= 8

    if nbits:
        out.append(bitbuf & 0xFF)

    return bytes(out)


def compress_safe_9bit(data: bytes, chunk_size=180):
    """
    Stream Bubble LZW headerless.
    Inserisce CLEAR ad ogni chunk per evitare qualsiasi transizione 9->10 bit.
    """
    if chunk_size < 1 or chunk_size > 240:
        raise ValueError("chunk_size consigliato 1..240")

    codes = []

    for pos in range(0, len(data), chunk_size):
        chunk = data[pos:pos + chunk_size]
        codes.append(CLEAR)
        codes.extend(lzw_codes_for_chunk(chunk))

    codes.append(END)
    return pack_9bit_lsb(codes)


def unpack_9bit_lsb(data: bytes):
    bitbuf = 0
    nbits = 0
    pos = 0

    while True:
        while nbits < 9:
            if pos >= len(data):
                return
            bitbuf |= data[pos] << nbits
            nbits += 8
            pos += 1

        code = bitbuf & 0x1FF
        bitbuf >>= 9
        nbits -= 9
        yield code


def verify_safe_stream(comp: bytes):
    dictionary = {i: bytes([i]) for i in range(256)}
    next_code = FIRST
    previous = None
    out = bytearray()

    for code in unpack_9bit_lsb(comp):
        if code == CLEAR:
            dictionary = {i: bytes([i]) for i in range(256)}
            next_code = FIRST
            previous = None
            continue

        if code == END:
            return bytes(out)

        if previous is None:
            if code not in dictionary:
                raise ValueError(f"Verify: primo codice non valido {code:04X}")
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
                f"Verify: codice non valido {code:04X}, next={next_code:04X}"
            )

        out += entry

        if next_code < 0x200:
            dictionary[next_code] = previous + entry[:1]
            next_code += 1

        previous = entry

    raise ValueError("Verify: END non trovato")


def save_encoded_preview(raw: bytes, path: Path):
    """
    Preview tecnica 320x200 dei quattro valori CGA 0..3.
    Serve solo per controllare la codifica; i colori reali sul PC1 dipendono dalla palette.
    """
    pal = [
        0, 0, 0,
        0, 255, 255,
        255, 0, 255,
        255, 255, 255,
    ] + [0, 0, 0] * 252

    pixels = []
    for b in raw:
        pixels.extend([
            (b >> 6) & 3,
            (b >> 4) & 3,
            (b >> 2) & 3,
            b & 3,
        ])

    img = Image.new("P", (320, 200))
    img.putpalette(pal)
    img.putdata(pixels)
    img.save(path)


def main():
    ap = argparse.ArgumentParser(
        description="Costruisce BBLOCKS.CCF PC1 da PNG logico 160x200 a 16 colori."
    )
    ap.add_argument("input_png")
    ap.add_argument("--out", default="BBLOCKS_NEW.CCF")
    ap.add_argument("--raw", default=None,
                    help="Salva anche il raw CGA 16000 byte")
    ap.add_argument("--preview", default=None,
                    help="Salva preview tecnica 320x200 CGA-coded")
    ap.add_argument("--chunk", type=int, default=180,
                    help="Dimensione chunk LZW safe (default 180)")
    args = ap.parse_args()

    src = Path(args.input_png)
    dst = Path(args.out)

    _, pixels, used = read_indices_160(src)

    print(f"Input:               {src}")
    print(f"Dimensioni:          160x200")
    print(f"Indici usati:        {used}")

    raw = encode_pc1_to_cga_raw(pixels)
    print(f"Raw CGA:             {len(raw)} byte")

    comp = compress_safe_9bit(raw, args.chunk)

    # Autoverifica obbligatoria.
    check = verify_safe_stream(comp)
    if check != raw:
        raise RuntimeError("Verifica LZW fallita: il raw ricostruito non coincide")

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(comp)

    if args.raw:
        Path(args.raw).write_bytes(raw)

    if args.preview:
        save_encoded_preview(raw, Path(args.preview))

    print(f"BBLOCKS.CCF creato:  {dst}")
    print(f"Dimensione CCF:      {len(comp)} byte")
    print("Verifica LZW:        OK")
    print("Header:              nessuno (stream LZW da offset 0)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        sys.exit(1)
