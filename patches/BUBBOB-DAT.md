# BUBBOB.DAT patches

These offsets were verified against the project copy of the DOS game. Check the expected original bytes before modifying another release.

## Invulnerability

```text
offset 0x944D
normal:         72
invulnerable:   EB
```

The following byte remains `3A`, so the observed pairs were `72 3A` and `EB 3A`.

## Initial level

```text
offset 0x0523..0x0524
word, little-endian
```

- level 1 = `FFFF`
- levels 2..100 = `level - 2`
- example: level 10 = `0008` -> bytes `08 00`

`BBCHEAT.ASM` implements this logic and validates the existing value before writing.

## PC1 procedural star field

PC1/CGA star routine: IDA `3590`. EGA has a separate routine (`619E`), allowing the PC1 star generator to be changed without changing EGA.

Patch `BUBBOB.DAT` `0x37A9..0x37E9`.

Original:

```text
E8 33 DD 3C 01 B0 00 73 0F E8 2A DD 8A C4 24 07
2E D7 22 C2 D0 CA D0 CA D0 CA D0 CA 8A F0 E8 15
DD 3C 01 8A C6 73 13 8A F0 E8 0A DD 8A C4 24 07
2E D7 22 C2 0A C6 D0 CA D0 CA D0 CA D0 CA AA E2
BF
```

PC1 version:

```text
E8 33 DD 3C 01 B0 00 73 11 E8 2A DD 8A C4 24 07
2E D7 D0 E0 D0 E0 D0 E0 D0 E0 8A F0 E8 17 DD 3C
01 B0 00 73 09 E8 0E DD 8A C4 24 07 2E D7 0A C6
AA E2 CD 90 90 90 90 90 90 90 90 90 90 90 90 90
90
```

Colour table at `0x37F3`:

```text
old: FF FF AA FF FF AA FF FF
new: 0F 0F 0F 0F 07 07 0E 0E
```

Resulting weighted logical PC1 colours:

- `F` white: 50%
- `7` light gray: 25%
- `E` bright yellow: 25%

## Vertical shadows

```text
runtime pattern: DS:46EE
runtime mask:    DS:46F9
DAT pattern:     0x10C12
DAT mask:        0x10C1D
```

Original pattern:

```text
40 50 54 55 55 55 55 55 15 05 01
```

PC1 pattern:

```text
80 80 88 88 88 88 88 88 88 08 08
```

Mask remains:

```text
3F 0F 03 00 00 00 00 00 C0 F0 FC
```

## Horizontal shadows

```text
runtime pattern: DS:470C
runtime mask:    DS:471C
DAT pattern:     0x10C30
DAT mask:        0x10C40
```

Original pattern:

```text
AA AA 00 00 2A AA 80 00 0A AA A0 00 02 AA A8 00
```

PC1 pattern:

```text
88 88 00 00 88 88 00 00 08 88 80 00 08 88 80 00
```

Original mask:

```text
00 00 FF FF C0 00 3F FF F0 00 0F FF FC 00 03 FF
```

PC1 mask:

```text
00 00 FF FF 00 00 FF FF F0 00 0F FF F0 00 0F FF
```

## Attract/ending text colour table

```text
IDA table:     CS:3B91
modified item: CS:3B93
runtime mask:  DS:F862
change:        55 -> 22
```

Original table:

```text
00 00 55 55 AA 00 AA FF 00 55 55 55 AA AA FF FF
```

Modified table:

```text
00 00 22 55 AA 00 AA FF 00 55 55 55 AA AA FF FF
```

## Historical copyright-string experiment

A copy of `(C) COPYRIGHT 1989 BY TAITO AMERICA CORP.` was found around DAT offset `0x02F3` (using the then-verified IDA-to-DAT `+0x0200` relation). Modifying this copy did **not** change the visible startup copyright. It is documented here only to prevent repeating that dead end; it is not a required port patch.
