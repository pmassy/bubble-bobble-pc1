# Bubble Bobble PC1 — Edizione 16 colori

## Il progetto

Questo progetto adatta graficamente la versione DOS del 1989 di **Bubble Bobble** alle capacità video dell'**Olivetti Prodest PC1**, dotato di controller Yamaha V6355D. Il PC1 dispone di una modalità estesa **160×200 a 16 colori** che il gioco originale non utilizza.

Non è un remake né una riscrittura: il lavoro nasce dal reverse engineering della versione DOS originale, dall'analisi dei formati grafici, dalla creazione di strumenti di estrazione/ricostruzione e da patch mirate. L'obiettivo è modificare il meno possibile il programma e preservare, dove possibile, la compatibilità con gli altri driver originali.

## Autori e contributi

- **Massimiliano Pascuzzi** — ideazione e coordinamento, reverse engineering, sviluppo del workflow, analisi e test, verifica su Olivetti Prodest PC1 reale.
- **Davide Ottonelli** — ridisegno e adattamento della grafica alla rappresentazione a doppio pixel orizzontale del PC1.
- **ChatGPT (OpenAI)** — assistenza al reverse engineering, analisi assembly e formati binari, sviluppo/revisione degli strumenti Python, patch binarie e documentazione tecnica.

### Ringraziamenti

Un ringraziamento a [rebb64](https://github.com/zaidka/rebb64), che ha gentilmente concesso l'uso dei blocchi estratti dalla versione Commodore 64 come riferimento per il lavoro grafico.

## Modalità PC1

Ogni pixel logico 16 colori viene codificato tramite due pixel CGA 2bpp:

```text
left  = (i >> 2) & 3
right = i & 3
```

Quindi un'immagine logica 160×200 diventa una rappresentazione codificata larga 320 pixel. Dettagli in `docs/PC1-VIDEO.md`.

## File interessati

Il repository **non distribuisce file originali del gioco**.

| File | Funzione | Intervento |
|---|---|---|
| `BUBBLE.EXE` | Loader e video | inizializzazione PC1 e patch renderer |
| `BUBBOB.DAT` | programma principale | patch grafiche e modifiche opzionali |
| `SPRITES.CCF` | sprite | estrazione, ridisegno, mask, conversione e rebuild |
| `BBLOCKS.CCF` | blocchi livelli | rebuild PC1 |
| `BBLOCKS.TCF` | grafica alternativa blocchi | usato per recuperare il CCF danneggiato |
| `TITLEPIC.CCF` | titolo | conversione e rebuild |
| `EXTEND.CCF` | schermata EXTEND | conversione e rebuild |
| `SECRET.CCF` | schermata SECRET | conversione e rebuild |
| `ARCADE.TCF` | schermata ARCADE | nuova sorgente 160×200 e adattamento renderer |

> `BBLOCKS.TCF` è stato usato soltanto perché il `BBLOCKS.CCF` della copia impiegata nello sviluppo era danneggiato. Non è un requisito generale.

# SPRITES.CCF

Gli strumenti sono in `tools/sprites/`.

### 1. Estrazione

```bat
py bb_extract_sprites_ccf.py SPRITES.CCF --out work_original --clean
```

### 2. Duplicati e mega-PNG

```bat
py bb_mark_duplicate_sprites.py work_original\sprites
```

Produce:

```text
sprites_duplicates_annotated.png
sprites_duplicates_report.txt
sprites_duplicates.csv
```

Durante lo sviluppo: **2848 immagini**, **547 gruppi unici**, **2301 duplicati**.

### 3. Ridisegno

Il mega-PNG viene modificato a 16 colori. Negli esempi il risultato è `SPRITES_16_COLOURS.png`.

### 4. Reimportazione

```bat
py bb_import_edited_sprite_sheet.py SPRITES_16_COLOURS.png work_original\sprites sprites_duplicates.csv work_edited\sprites --clean
```

### 5. Preparazione directory PC1

La directory finale deve contenere anche `manifest.json` e `source\` provenienti dall'estrazione originale:

```bat
copy work_original\manifest.json work_pc1\manifest.json
xcopy work_original\source work_pc1\source /E /I /Y
```

### 6. Conversione degli sprite PC1

```bat
py bb_convert_sprite16_to_pc1.py work_edited\sprites work_pc1\sprites
```

**Convertire solo gli sprite grafici, non le mask.** La conversione va fatta **prima** di inserire le mask definitive.

```text
reimport sprite -> conversione PC1 -> merge mask -> build
```

### 7. Mask

Le mask sono state ricavate da un secondo mega-PNG nel quale le parti nere realmente appartenenti agli sprite vengono temporaneamente rese non nere. In questo modo il nero dello sfondo resta distinguibile dal nero opaco dello sprite.

### 8. Merge mask

Solo dopo la conversione PC1:

```bat
robocopy work_masks\sprites work_pc1\sprites phase_*_mask.png /S
```

Dopo il merge **non eseguire nuovamente la conversione PC1** sulla directory risultante.

### 9. Rebuild

```bat
py bb_build_sprites_ccf.py work_pc1 --import-masks --out build\SPRITES.CCF
```

# BBLOCKS.CCF

Gli strumenti sono in `tools/bblocks/`.

La sorgente è 160×200 a 16 colori indicizzati. Quando la palette non è certamente corretta, conviene normalizzarla:

```bat
py make_indexed_precise.py BBLOCKS_160x200.png BBLOCKS_160x200_INDEXED.png
```

Poi:

```bat
py bb_build_bblocks_pc1.py BBLOCKS_160x200_INDEXED.png --out build\BBLOCKS.CCF
```

Con raw e preview:

```bat
py bb_build_bblocks_pc1.py BBLOCKS_160x200_INDEXED.png --out build\BBLOCKS.CCF --raw build\BBLOCKS.raw --preview build\BBLOCKS_preview.png
```

# Schermate statiche

Gli strumenti sono in `tools/static/`.

### TITLEPIC

```bat
py bb_extract_static_ccf.py TITLEPIC.CCF --out work_titlepic --clean
py bb_pc1_encode_160_to_cga320.py TITLEPIC_160x200.png TITLEPIC_pc1.png --preview
py bb_build_static_ccf.py work_titlepic --out build\TITLEPIC.CCF
```

L'immagine convertita va usata come nuova immagine `TITLEPIC` nella directory estratta prima del build.

### EXTEND

```bat
py bb_extract_static_ccf.py EXTEND.CCF --out work_extend --clean
py bb_pc1_encode_160_to_cga320.py EXTEND_160x200.png EXTEND_pc1.png --preview
py bb_build_static_ccf.py work_extend --out build\EXTEND.CCF
```

### SECRET

```bat
py bb_extract_static_ccf.py SECRET.CCF --out work_secret --clean
py bb_pc1_encode_160_to_cga320.py SECRET_160x200.png SECRET_pc1.png --preview
py bb_build_static_ccf.py work_secret --out build\SECRET.CCF
```

# ARCADE.TCF

Gli strumenti sono in `tools/arcade/`.

```bat
py bb_extract_arcade_tcf.py ARCADE.TCF --out work_arcade --clean
```

L'estrazione produce `work_arcade\image\ARCADE.png` a 320×200. Sostituirlo con la nuova immagine **160×200 a 16 colori**, mantenendo il nome `ARCADE.png`.

```bat
py bb_build_arcade_tcf_pc1.py work_arcade --out build\ARCADE.TCF
```

Il builder converte il PNG in 4bpp packed, conserva la tail originale, ricomprime e verifica automaticamente il risultato ridecomprimendolo. La nuova parte grafica occupa 16000 byte decompressi.

Il cambio di larghezza ha richiesto l'adattamento dei renderer **PC1, EGA e Tandy**. Dettagli e byte delle patch: `patches/BUBBLE-EXE.md`.

# BUBBLE.EXE

Le patch riguardano inizializzazione PC1 e renderer PC1/EGA/Tandy. Vedere `patches/BUBBLE-EXE.md`. Il repository non distribuisce l'eseguibile originale né quello modificato.

# BUBBOB.DAT

`BUBBOB.DAT` è un eseguibile DOS compresso EXEPACK. Per l'analisi statica:

```bat
py unexepack_py.py BUBBOB.DAT BUBBOB_UNPACKED.EXE
```

L'unpacked serve per IDA/analisi; il gioco continua a usare `BUBBOB.DAT`. Le patch verificate sono documentate in `patches/BUBBOB-DAT.md`.

# BBCHEAT.COM

`tools/cheats/BBCHEAT.ASM` è un'utility 8086/DOS per attivare/disattivare l'invulnerabilità e impostare il livello iniziale 1..100. Valida i byte prima di modificarli. È stata assemblata e testata con **TASM 1.0**.

# Requisiti

- Python 3
- Pillow
- una propria copia compatibile della versione DOS di Bubble Bobble

```bat
pip install -r requirements.txt
```

# Struttura

```text
bubble-bobble-pc1/
├ README.md
├ requirements.txt
├ docs/
│  ├ PC1-VIDEO.md
│  ├ FORMATS.md
│  ├ SPRITES.md
│  ├ REVERSE-ENGINEERING.md
│  └ PROJECT-STATUS.md
├ patches/
│  ├ BUBBLE-EXE.md
│  └ BUBBOB-DAT.md
└ tools/
   ├ arcade/
   ├ bblocks/
   ├ static/
   ├ sprites/
   ├ ida/
   ├ cheats/
   └ common/
```

# Stato e copyright

Il repository documenta le parti sufficientemente stabili e verificate. Una parte significativa del risultato è stata provata sul vero Olivetti Prodest PC1.

Non vengono distribuiti `BUBBLE.EXE`, `BUBBOB.DAT`, CCF/TCF originali, eseguibili modificati, sprite o altre risorse grafiche originali. Gli strumenti richiedono i file provenienti dalla copia dell'utente.

Bubble Bobble, personaggi, grafica originale, marchi e materiali del gioco appartengono ai rispettivi titolari. Il progetto è indipendente e non è affiliato né approvato da Taito.

La licenza degli strumenti e della documentazione del progetto non concede diritti sui materiali del gioco originale. La scelta della licenza del repository verrà formalizzata separatamente.
