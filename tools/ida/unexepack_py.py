from pathlib import Path
import argparse
import struct
import sys


DOS_SIGNATURE = 0x5A4D      # MZ
EXEPACK_SIGNATURE = 0x4252  # RB
ERROR_STRING = b"Packed file is corrupt"


def u16(data, off):
    return struct.unpack_from("<H", data, off)[0]


def p16(value):
    return struct.pack("<H", value & 0xFFFF)


def parse_dos_header(data):
    if len(data) < 28:
        raise ValueError("File troppo piccolo per essere un EXE DOS.")

    fields = struct.unpack_from("<14H", data, 0)
    names = [
        "e_magic", "e_cblp", "e_cp", "e_crlc",
        "e_cparhdr", "e_minalloc", "e_maxalloc",
        "e_ss", "e_sp", "e_csum",
        "e_ip", "e_cs", "e_lfarlc", "e_ovno"
    ]
    h = dict(zip(names, fields))

    if h["e_magic"] != DOS_SIGNATURE:
        raise ValueError("Non è un EXE DOS MZ valido.")

    return h


def parse_exepack_header(data, off):
    if off + 18 > len(data):
        raise ValueError("Header EXEPACK fuori file.")

    fields = struct.unpack_from("<9H", data, off)
    names = [
        "real_ip", "real_cs", "mem_start", "exepack_size",
        "real_sp", "real_ss", "dest_len", "skip_len", "signature"
    ]
    h = dict(zip(names, fields))

    if h["signature"] != EXEPACK_SIGNATURE and h["skip_len"] != EXEPACK_SIGNATURE:
        raise ValueError(
            f"Firma EXEPACK non valida. skip_len={h['skip_len']:04X}, "
            f"signature={h['signature']:04X}"
        )

    if h["exepack_size"] == 0:
        raise ValueError("EXEPACK size nullo.")

    return h


def reverse_bytes(b):
    return bytearray(reversed(b))


def unpack_exepack_data(packed, dest_max):
    """
    EXEPACK lavora all'indietro.
    Qui invertiamo il blocco, applichiamo i comandi, poi reinvertiamo l'output.
    """
    buf = reverse_bytes(packed)
    pos = 0
    out = bytearray()

    while pos < len(buf) and buf[pos] == 0xFF:
        pos += 1

    while pos < len(buf):
        if pos + 3 > len(buf):
            break

        opcode = buf[pos]
        pos += 1

        # Attenzione: dopo il reverse, il count è letto big-endian.
        count = (buf[pos] << 8) | buf[pos + 1]
        pos += 2

        if (opcode & 0xFE) == 0xB0:
            if pos >= len(buf):
                raise ValueError("Comando fill senza byte di riempimento.")
            fillbyte = buf[pos]
            pos += 1

            if len(out) + count > dest_max:
                raise ValueError("Overflow durante fill.")
            out.extend([fillbyte] * count)

        elif (opcode & 0xFE) == 0xB2:
            if pos + count > len(buf):
                raise ValueError("Comando copy oltre fine dati compressi.")

            if len(out) + count > dest_max:
                raise ValueError("Overflow durante copy.")
            out.extend(buf[pos:pos + count])
            pos += count

        else:
            raise ValueError(f"Opcode EXEPACK sconosciuto: {opcode:02X} a pos {pos-3:X}")

        if opcode & 1:
            break

    # Eventuale coda dati residua.
    if pos < len(buf):
        remaining = buf[pos:]
        if len(out) + len(remaining) > dest_max:
            raise ValueError("La coda residua eccede la dimensione destinazione.")
        out.extend(remaining)

    out = reverse_bytes(out)
    return bytes(out)


def create_relocation_table(data, dos_h, exepack_h, exepack_offset):
    search_area = data[exepack_offset:]
    rel = search_area.find(ERROR_STRING)

    if rel < 0:
        raise ValueError('Stringa "Packed file is corrupt" non trovata.')

    reloc_pos = exepack_offset + rel + len(ERROR_STRING)
    exepack_end = exepack_offset + exepack_h["exepack_size"]

    reloc_entries = bytearray()

    pos = reloc_pos
    for segment_index in range(16):
        if pos + 2 > len(data):
            raise ValueError("Tabella relocation tronca.")

        count = u16(data, pos)
        pos += 2

        for _ in range(count):
            if pos + 2 > len(data):
                raise ValueError("Entry relocation troncata.")

            entry = u16(data, pos)
            pos += 2

            reloc_entries += p16(entry)
            reloc_entries += p16((segment_index * 0x1000) & 0xFFFF)

    if pos > exepack_end:
        print(
            f"ATTENZIONE: relocation table oltre exepack_end "
            f"pos={pos:05X}, end={exepack_end:05X}"
        )

    return bytes(reloc_entries)


def craft_exe(original_h, exepack_h, unpacked_data, reloc):
    """
    Ricostruisce un EXE DOS non compresso con header MZ e relocation table.
    """
    header_size = 28 + len(reloc)

    # Come unEXEPACK: header allineato a blocchi da 512 byte.
    e_cparhdr = header_size // 16
    e_cparhdr = (e_cparhdr // 32 + 1) * 32

    padding_len = e_cparhdr * 16 - header_size
    total_length = header_size + padding_len + len(unpacked_data)

    e_cblp = total_length % 512
    e_cp = total_length // 512 + 1

    new_h = {
        "e_magic": DOS_SIGNATURE,
        "e_cblp": e_cblp,
        "e_cp": e_cp,
        "e_crlc": len(reloc) // 4,
        "e_cparhdr": e_cparhdr,
        "e_minalloc": original_h["e_minalloc"],
        "e_maxalloc": 0xFFFF,
        "e_ss": exepack_h["real_ss"],
        "e_sp": exepack_h["real_sp"],
        "e_csum": 0,
        "e_ip": exepack_h["real_ip"],
        "e_cs": exepack_h["real_cs"],
        "e_lfarlc": 28,
        "e_ovno": 0,
    }

    header = struct.pack(
        "<14H",
        new_h["e_magic"],
        new_h["e_cblp"],
        new_h["e_cp"],
        new_h["e_crlc"],
        new_h["e_cparhdr"],
        new_h["e_minalloc"],
        new_h["e_maxalloc"],
        new_h["e_ss"],
        new_h["e_sp"],
        new_h["e_csum"],
        new_h["e_ip"],
        new_h["e_cs"],
        new_h["e_lfarlc"],
        new_h["e_ovno"],
    )

    return header + reloc + (b"\x00" * padding_len) + unpacked_data, new_h


def print_header(title, h):
    print(title)
    for k, v in h.items():
        print(f"  {k:12s} = {v:04X}")


def main():
    ap = argparse.ArgumentParser(description="Unpacker Python per Microsoft EXEPACK DOS EXE.")
    ap.add_argument("input", help="EXE/DAT packed, es. BUBBOB.DAT")
    ap.add_argument("output", nargs="?", default="BUBBOB_UNPACKED.EXE", help="Output unpacked EXE")
    args = ap.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    data = in_path.read_bytes()

    dos_h = parse_dos_header(data)
    exepack_offset = (dos_h["e_cparhdr"] + dos_h["e_cs"]) * 16
    exepack_h = parse_exepack_header(data, exepack_offset)

    print_header("DOS header originale:", dos_h)
    print(f"\nEXEPACK header offset = {exepack_offset:05X}")
    print_header("EXEPACK header:", exepack_h)

    packed_start = dos_h["e_cparhdr"] * 16
    packed_end = exepack_offset
    packed = data[packed_start:packed_end]

    dest_max = exepack_h["dest_len"] * 16

    print(f"\nPacked data:   {packed_start:05X}-{packed_end:05X} ({len(packed)} byte)")
    print(f"Dest max:      {dest_max} byte")

    unpacked = unpack_exepack_data(packed, dest_max)
    print(f"Unpacked data: {len(unpacked)} byte")

    reloc = create_relocation_table(data, dos_h, exepack_h, exepack_offset)
    print(f"Relocation:    {len(reloc)//4} entries, {len(reloc)} byte")

    exe, new_h = craft_exe(dos_h, exepack_h, unpacked, reloc)

    print_header("\nDOS header nuovo:", new_h)

    out_path.write_bytes(exe)
    print(f"\nCreato: {out_path}")
    print(f"Dimensione output: {len(exe)} byte")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        sys.exit(1)