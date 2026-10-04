# Bubble Bobble DOS graphics formats

## Purpose

This document collects the structures actually analysed during the project. The `.CCF` and `.TCF` extensions are **not treated as universal format specifications**: files sharing the same extension may have different structures and workflows.

## Bubble LZW

Several resources use an LZW variant with codes read LSB-first:

```text
CLEAR      = 0x100
END        = 0x101
FIRST_FREE = 0x102
MAX_BITS   = 12
```

The initial dictionary contains bytes `0x00..0xFF`; the initial code width is 9 bits and the decoder supports growth up to 12 bits.

### Safe 9-bit recompression

Some builders use a conservative strategy that periodically emits `CLEAR` codes to keep codes at 9 bits. The goal is compatibility rather than maximum compression. The `ARCADE.TCF` builder, for example, uses 180-byte chunks by default and verifies the result by decompressing it again.

## Packed 4bpp

Some 16-colour resources use packed 4 bits per pixel:

```text
1 byte = 2 pixels
0xAB -> left 0xA, right 0xB
```

Therefore:

```text
320×200 = 32000 bytes
160×200 = 16000 bytes
```

## ARCADE.TCF

The file contains a 2-byte header followed by a Bubble LZW stream. The original decompressed data contains a **320×200 packed 4bpp** image occupying 32000 bytes, followed by any additional data treated as a `tail`.

The extractor preserves the original file, raw data, image raw data, tail, PNG and manifest. In this project the new image is **160×200 packed 4bpp** (16000 bytes). The builder constructs:

```text
[new 16000-byte image] + [original tail]
```

then recompresses and verifies the result.

```bat
py bb_extract_arcade_tcf.py ARCADE.TCF --out work_arcade --clean
```

Extraction creates `work_arcade\image\ARCADE.png` at 320×200. For the modified file it must be replaced by the new **160×200 16-colour** `ARCADE.png`.

```bat
py bb_build_arcade_tcf_pc1.py work_arcade --out build\ARCADE.TCF
```

Changing the source width requires patches to the PC1, EGA and Tandy renderers; see `patches/BUBBLE-EXE.md`.

## BBLOCKS.TCF

This file was used as a recovery source because the `BBLOCKS.CCF` in the game copy used during development was damaged. It is not a general requirement.

Decompressing the file analysed during the project produces **32032 bytes**: the first 32000 bytes are a 320×200 packed 4bpp image, followed by 32 additional bytes. Colour indices 0..15 are the significant graphics data; the RGB palette used for export is only a working palette.

## BBLOCKS.CCF

The PC1 version is built from a logical **160×200 16-colour indexed PNG**. Double-pixel encoding produces a **320×200 2bpp** raw image of 16000 bytes, which is then compressed into the format used by the game.

When needed, the palette should be normalized first:

```bat
py make_indexed_precise.py BBLOCKS_160x200.png BBLOCKS_160x200_INDEXED.png
py bb_build_bblocks_pc1.py BBLOCKS_160x200_INDEXED.png --out build\BBLOCKS.CCF
```

## Static CCF files

`TITLEPIC.CCF`, `EXTEND.CCF` and `SECRET.CCF` use the following workflow:

```text
extract -> replace image -> PC1 encoding -> build
```

The structure required for rebuilding is preserved in the working directory. `bb_pc1_encode_160_to_cga320.py` converts the logical 160×200 source into the PC1 representation.

## SPRITES.CCF

This resource is more complex than the static screens. Extraction produces blocks and phases, for example:

```text
sprites\
  block_0000\
    phase_0_image.png
    phase_0_mask.png
```

The working directory also contains `manifest.json` and `source\`, which are required for rebuilding.

The `image` files must be converted to PC1 encoding; the `mask` files **must not be converted**. The complete workflow is documented in `docs/SPRITES.md`.

## Duplicate sprites

`bb_mark_duplicate_sprites.py` compares RGBA images using SHA-1 and groups them as `UNIQUE`, `MASTER` and `DUPLICATE`. During this project 2848 sprites were analysed: 547 unique groups and 2301 duplicate occurrences. The mapping is written to `sprites_duplicates.csv`.

## Indexed PNG files

Two visually identical PNG files may use different palette indices. When the binary format uses the index directly, this difference matters. Where necessary, the tools therefore work explicitly with indices 0..15.

## Manifest and source

Extractors may create:

```text
manifest.json
source\
image\ or sprites\
```

`manifest.json` describes the structure required for rebuilding; `source\` preserves original data that must be retained. Working directories are therefore part of the conversion process, not merely temporary PNG folders.

## Linear raw data and video memory

The raw data described here is generally linear. The physical interleaved CGA layout at `B800h` is a separate issue and is handled by the video code when necessary. See `docs/PC1-VIDEO.md`.

## General principle

The tools try to modify only the required portion and preserve everything from the original file that does not need to change. A resource's structure should not be inferred solely from its `.CCF` or `.TCF` extension.
