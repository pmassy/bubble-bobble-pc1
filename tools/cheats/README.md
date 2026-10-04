# BBCHEAT.COM

`BBCHEAT.ASM` is an 8086 DOS `.COM` utility used during the project to simplify testing.

It opens `BUBBOB.DAT` for read/write access and validates the expected values before changing them.

Features:

```text
1 - Enable invulnerability
2 - Disable invulnerability
3 - Set initial level (1..100)
0 - Exit
```

The source uses:

```text
invulnerability byte: 0x944D
initial-level word:   0x0523
```

`BBCHEAT.ASM` was assembled and tested during the project with **TASM 1.0**.

Typical build:

```bat
tasm BBCHEAT.ASM
tlink /t BBCHEAT.OBJ
```

Keep the generated `BBCHEAT.COM` next to `BUBBOB.DAT` when using it.
