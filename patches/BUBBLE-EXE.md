# BUBBLE.EXE patches

Offsets below refer to the analyzed code locations used during the project. Always verify against the exact game version before patching.

## PC1/CGA ARCADE renderer

At IDA `seg001:40DE`:

```text
B9 28 00 F3 A5 EB 3B 90 90 90
```

Equivalent:

```asm
mov cx,28h       ; 40 words = 80 bytes
rep movsw        ; one 160-pixel PC1 row
jmp short 4120h
nop
nop
nop
```

80 bytes × 200 rows = 16,000 source bytes. The surrounding code performs the CGA B800 even/odd scan-line interleave.

## EGA ARCADE renderer for the 160×200 source

At IDA `seg001:3FFC`, replace the old 320-wide conversion loop with:

```text
B8 08 C0 EF 8A 04 D0 E8 D0 E8 D0 E8 D0 E8 26 86
05 B8 08 30 EF AC 24 0F 26 86 05 B8 08 0C EF 8A
04 D0 E8 D0 E8 D0 E8 D0 E8 26 86 05 B8 08 03 EF
AC 24 0F 26 86 05 47 E2 C7
```

Fill IDA `4035` through `4062` with `90` (NOP). Original code resumes at `4063` with `1F BA C4 03 ...`.

The four EGA masks are:

```text
C0 30 0C 03
```

The conversion expands:

```text
source: A B C D
EGA:    A A B B C C D D
```

The loop still executes 8,000 iterations but consumes two source bytes per iteration: exactly 16,000 bytes.

For the binary version verified at the end of development, the corresponding file layout around this patch was:

```text
B9 40 1F  at file 0x43D9
patch     starts at file 0x43DC
new code  through file 0x4414
NOP       file 0x4415..0x4442
original  resumes file 0x4443 (1F BA C4 03 ...)
```

## Tandy ARCADE renderer for the 160×200 source

Verified mapping in this area:

```text
FILE = IDA + 0x3E0
```

At file offset `0x4489` (IDA `40A9`) replace:

```text
B9 50 00 F3 A5
```

with:

```text
E8 3C 00 90 90
```

This calls a helper placed in the now-unused PC1 region at file `0x44C8..0x44FF` (IDA `40E8..411F`):

```text
53 BB 08 41 B9 50 00 AC 8A E0 D0 E8 D0 E8 D0 E8
D0 E8 2E D7 AA 8A C4 24 0F 2E D7 AA E2 E9 5B C3
00 11 22 33 44 55 66 77 88 99 AA BB CC DD EE FF
90 90 90 90 90 90 90 90
```

Il helper legge 80 byte sorgente per riga e trasforma ogni byte 4bpp `AB` in due byte `AA BB`, ottenendo i 160 byte per riga richiesti dal framebuffer Tandy. La lookup table è `00 11 22 ... FF`.

Il codice originale riprende a file `0x4500` / IDA `4120`. La patch è stata verificata durante lo sviluppo.
