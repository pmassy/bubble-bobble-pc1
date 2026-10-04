# Olivetti Prodest PC1 16-colour video mode

## Purpose

This document describes the **Olivetti Prodest PC1** graphics mode used by the project and the encoding adopted by the repository tools. It is not intended as complete documentation for the Yamaha V6355D controller: it only covers the aspects actually used and verified during the project.

## Video mode used

The Prodest PC1 uses a **Yamaha V6355D** video controller. The project takes advantage of an extended **160×200 16-colour** mode that the original DOS version of Bubble Bobble does not use directly.

The modified game initializes the mode with:

```asm
mov dx,03D8h
mov al,04Ah
out dx,al
inc dx
mov al,20h
out dx,al
retn
```

Corresponding bytes:

```text
BA D8 03 B0 4A EE 42 B0 20 EE C3
```

The `BUBBLE.EXE` patch is documented in `patches/BUBBLE-EXE.md`.

## 16-colour representation

One logical 16-colour pixel is represented by **two horizontally adjacent CGA 2bpp pixels**. Given a colour index `i` from 0 to 15:

```text
left  = (i >> 2) & 3
right = i & 3
```

| Index | Left | Right | Index | Left | Right |
|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 8  | 2 | 0 |
| 1 | 0 | 1 | 9  | 2 | 1 |
| 2 | 0 | 2 | 10 | 2 | 2 |
| 3 | 0 | 3 | 11 | 2 | 3 |
| 4 | 1 | 0 | 12 | 3 | 0 |
| 5 | 1 | 1 | 13 | 3 | 1 |
| 6 | 1 | 2 | 14 | 3 | 2 |
| 7 | 1 | 3 | 15 | 3 | 3 |

Examples: `2 -> (0,2)`, `5 -> (1,1)`, `8 -> (2,0)`, `15 -> (3,3)`.

## Logical pixels and the "double pixel"

**160×200** is the logical 16-colour resolution. Each logical pixel occupies two pixels in the CGA representation, so 160 logical pixels become 320 encoded pixels.

The informal term **double pixel** does not mean simple pixel duplication: the two pixels contain the two halves of the 4-bit colour index. For example, `8 = 1000b` is split into `10 | 00`, producing `(2,0)`.

## Logical palette

The tools use indices 0..15 with the following working palette:

| Index | RGB | Index | RGB |
|---:|---|---:|---|
| 0 | 0,0,0 | 8 | 85,85,85 |
| 1 | 0,0,170 | 9 | 85,85,255 |
| 2 | 0,170,0 | 10 | 85,255,85 |
| 3 | 0,170,170 | 11 | 85,255,255 |
| 4 | 170,0,0 | 12 | 255,85,85 |
| 5 | 170,0,170 | 13 | 255,85,255 |
| 6 | 170,85,0 | 14 | 255,255,85 |
| 7 | 170,170,170 | 15 | 255,255,255 |

For conversion, the **palette index** is often more important than its RGB value. This is why some workflows use indexed PNG files and `make_indexed_precise.py`.

## Static-image conversion

The general process is:

```text
160×200 / 16 colours -> indices 0..15 -> split 4-bit index -> two CGA 2bpp pixels -> encoded 320×200 image
```

`bb_pc1_encode_160_to_cga320.py` is used, for example, with `TITLEPIC.CCF`, `EXTEND.CCF` and `SECRET.CCF`.

## CGA video memory

The PC1 driver uses video memory starting at `B800h`. The physical CGA layout is interleaved: even and odd scan lines belong to different memory areas. Assets are generally prepared as linear raw data; the game's video code arranges them in video memory when required.

## EGA and Tandy

The PC1 encoding must not be confused with the EGA and Tandy renderers. In the case of `ARCADE.TCF`, the new source is 160×200 with 16 colours, but PC1, EGA and Tandy require separate renderers. The corresponding patches are documented in `patches/BUBBLE-EXE.md`.

## Verification on real hardware

Video initialization, static screens, blocks, sprites, masks, colours, shadows and game sequences were also verified during development on a **real Olivetti Prodest PC1**.

## Terminology

- **Logical pixel**: one pixel of the 160×200 16-colour image.
- **Colour index**: the 0..15 value of a logical pixel.
- **Double pixel**: the pair of CGA 2bpp pixels representing one logical pixel.
- **Logical image**: the 160×200 source image.
- **PC1-encoded image**: the representation obtained by converting logical pixels into CGA pairs.
- **Linear raw**: graphics data before any physical arrangement in CGA video memory.
