# SPRITES.CCF workflow

This document describes the workflow actually used in the project. Images and masks are handled separately: **sprite images are converted to PC1 format; masks are not**.

## Extraction

```bat
py bb_extract_sprites_ccf.py SPRITES.CCF --out work_original --clean
```

## Mega-PNG and duplicate detection

```bat
py bb_mark_duplicate_sprites.py work_original\sprites
```

Main outputs:

```text
sprites_duplicates_annotated.png
sprites_duplicates_report.txt
sprites_duplicates.csv
```

The annotated mega-PNG is redrawn in 16 colours. During the project, 2848 sprites were analysed, resulting in 547 unique groups and 2301 duplicate occurrences.

## Reimporting the edited mega-PNG

```bat
py bb_import_edited_sprite_sheet.py SPRITES_16_COLOURS.png work_original\sprites sprites_duplicates.csv work_edited\sprites --clean
```

## Preparing `work_pc1`

Before building, `work_pc1` must also contain `manifest.json` and `source\` from `work_original`:

```bat
copy work_original\manifest.json work_pc1\manifest.json
xcopy work_original\source work_pc1\source /E /I /Y
```

## Converting sprite images to PC1 format

Run this **before merging the final masks**:

```bat
py bb_convert_sprite16_to_pc1.py work_edited\sprites work_pc1\sprites
```

Only sprite images must be converted. **Do not convert the masks.**

## Final masks

A second mega-PNG was used for mask generation. In this image, black areas that must remain opaque are temporarily painted with a non-black colour. This makes it possible to distinguish transparent black from black pixels that genuinely belong to a sprite.

Once the final masks are ready, merge them only **after** converting the sprite images:

```bat
robocopy work_masks\sprites work_pc1\sprites phase_*_mask.png /S
```

Do not run `bb_convert_sprite16_to_pc1.py` again after this merge.

The required order is therefore:

```text
edited mega-PNG
      |
      v
reimport sprite images
      |
      v
convert sprite images to PC1 format
      |
      v
merge final masks
      |
      v
build SPRITES.CCF
```

## Build

The final structure must be:

```text
work_pc1\
  manifest.json
  source\
  sprites\
    phase_*_image.png   (PC1-converted)
    phase_*_mask.png    (final masks, not converted)
```

Rebuild with:

```bat
py bb_build_sprites_ccf.py work_pc1 --import-masks --out build\SPRITES.CCF
```
