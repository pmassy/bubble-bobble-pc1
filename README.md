# Bubble Bobble PC1 — Edizione 16 colori

## Il progetto

Questo progetto nasce con l'obiettivo di adattare graficamente la versione DOS del 1989 di **Bubble Bobble** alle particolari capacità video dell'**Olivetti Prodest PC1**, dotato del controller video Yamaha V6355D.

La versione DOS originale supporta diversi adattatori grafici dell'epoca, tra cui CGA, EGA e Tandy. Il Prodest PC1 è compatibile con la grafica CGA, ma dispone anche di una modalità estesa **160×200 a 16 colori** che il gioco originale non utilizza.

L'idea alla base del progetto è stata quindi capire se fosse possibile sfruttare questa modalità per realizzare una versione graficamente più ricca di Bubble Bobble sul PC1, mantenendo per quanto possibile intatta la struttura del gioco originale.

Non si tratta di un remake né di una riscrittura del gioco.

Il lavoro è stato realizzato attraverso il reverse engineering della versione DOS originale, l'analisi dei suoi formati grafici, la creazione di strumenti per estrarre e ricostruire le risorse e alcune patch mirate al codice originale. Uno degli obiettivi è stato quello di modificare il meno possibile il funzionamento originale del programma. Dove possibile, le modifiche sono state limitate ai driver grafici e ai dati strettamente necessari alla nuova modalità PC1.

Un altro obiettivo è stato quello di preservare la compatibilità con gli altri sistemi grafici originali. Per esempio, la nuova schermata `ARCADE.TCF`, pur essendo stata ridisegnata utilizzando una sorgente 160×200, viene correttamente visualizzata anche utilizzando i driver EGA e Tandy, grazie a specifiche modifiche dei rispettivi renderer.

Il progetto ha soprattutto uno scopo tecnico, storico e didattico: studiare il funzionamento di un gioco DOS commerciale della fine degli anni '80 e sperimentare ciò che l'hardware del Prodest PC1 avrebbe potuto offrire se fosse stato sfruttato specificamente.

## Autori e contributi

### Massimiliano Pascuzzi

Ideazione e coordinamento del progetto, reverse engineering, analisi e test delle modifiche, sviluppo del workflow grafico e verifica sul vero hardware Olivetti Prodest PC1.

### Davide Ottonelli

Ridisegno e adattamento della grafica del gioco alla rappresentazione a doppio pixel orizzontale richiesta dalla modalità 160×200 a 16 colori del PC1.

Una parte importante del lavoro grafico è consistita nel ridisegnare gli sprite e gli elementi del gioco tenendo conto non soltanto dei 16 colori disponibili, ma anche della particolare geometria dei pixel di questa modalità video.

### ChatGPT (OpenAI)

Assistenza al reverse engineering, analisi del codice assembly e dei formati binari, sviluppo e revisione degli strumenti Python, progettazione delle patch binarie e documentazione tecnica.

Il lavoro è stato svolto in maniera iterativa: analisi del codice, formulazione delle modifiche, test in emulazione e verifica del risultato sull'hardware reale.

### Ringraziamenti

Un ringraziamento particolare va al progetto [**rebb64**](https://github.com/zaidka/rebb64), che è stato prezioso per lo studio della grafica della versione Commodore 64 di Bubble Bobble e ci ha permesso di utilizzare i blocchi estratti da tale versione come base per il lavoro grafico.

La grafica originale di Bubble Bobble e i relativi diritti rimangono naturalmente di proprietà dei rispettivi titolari.

## La modalità video del PC1

La modalità utilizzata dal progetto è una modalità estesa del controller Yamaha V6355D che permette di ottenere **160×200 pixel a 16 colori**.

Dal punto di vista della rappresentazione grafica, ogni pixel logico a 16 colori viene codificato utilizzando due pixel CGA 2bpp adiacenti. Per un indice colore `i` compreso tra 0 e 15:

```text
left  = (i >> 2) & 3
right = i & 3
```

Per esempio:

```text
colore 8  -> (2,0)
colore 2  -> (0,2)
colore 5  -> (1,1)
colore 15 -> (3,3)
```

Di conseguenza, un'immagine logica larga 160 pixel viene rappresentata come un'immagine codificata larga 320 pixel. Questo principio è alla base degli strumenti di conversione presenti nel repository. Per i dettagli tecnici vedere `docs/PC1-VIDEO.md`.

## File originali interessati dal progetto

Il progetto interviene su diversi file della versione DOS originale di Bubble Bobble. **Nessuno di questi file originali viene distribuito nel repository.**

| File | Contenuto / funzione | Intervento |
|---|---|---|
| `BUBBLE.EXE` | Loader e gestione video | inizializzazione PC1 e patch dei renderer |
| `BUBBOB.DAT` | programma principale del gioco | patch grafiche e modifiche opzionali |
| `SPRITES.CCF` | sprite del gioco | estrazione, ridisegno, mask, conversione e ricostruzione |
| `BBLOCKS.CCF` | elementi grafici dei livelli | ricostruzione della versione PC1 |
| `BBLOCKS.TCF` | grafica alternativa dei blocchi | utilizzato durante lo sviluppo per recuperare i blocchi |
| `TITLEPIC.CCF` | schermata del titolo | estrazione, conversione e ricostruzione |
| `EXTEND.CCF` | schermata EXTEND | estrazione, conversione e ricostruzione |
| `SECRET.CCF` | schermata SECRET | estrazione, conversione e ricostruzione |
| `ARCADE.TCF` | schermata ARCADE | conversione 160×200 e adattamento dei renderer |

### Nota su BBLOCKS.TCF

Nella copia del gioco utilizzata durante lo sviluppo, `BBLOCKS.CCF` risultava danneggiato. Per questo motivo `BBLOCKS.TCF` è stato utilizzato come sorgente alternativa per recuperare correttamente la grafica dei blocchi.

L'utilizzo del `.TCF` deriva quindi esclusivamente da questa circostanza: non è un requisito generale del processo di conversione di `BBLOCKS.CCF`.

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

`BBLOCKS.CCF` contiene gli elementi grafici utilizzati per costruire i livelli. Gli strumenti dedicati si trovano in `tools/bblocks/`.

Come spiegato sopra, durante questo progetto abbiamo utilizzato `BBLOCKS.TCF` come sorgente soltanto perché il `BBLOCKS.CCF` presente nella nostra copia del gioco risultava danneggiato. Il repository comprende quindi anche uno strumento per estrarre e rendere visibile la grafica contenuta nel TCF.

### Estrazione dei blocchi da BBLOCKS.TCF

Partendo dal file originale:

```bat
py bb_extract_bblocks_tcf.py BBLOCKS.TCF --out work_bblocks_tcf --clean
```

Lo script decomprime lo stream Bubble LZW e crea una directory di lavoro che comprende il PNG estratto e i dati necessari a documentare l'operazione:

```text
work_bblocks_tcf\
    manifest.json
    source\
        BBLOCKS.TCF.original
        BBLOCKS.TCF.raw
        BBLOCKS.image_32000.raw
        BBLOCKS.tail.bin
    image\
        BBLOCKS.png
```

`BBLOCKS.png` rappresenta la grafica estratta dal TCF come immagine indicizzata **320×200 a 16 colori**. I primi 32000 byte decompressi sono interpretati come grafica packed 4bpp, con il nibble alto corrispondente al pixel sinistro e il nibble basso al pixel destro. Gli eventuali byte successivi vengono conservati separatamente in `BBLOCKS.tail.bin`.

Nel nostro caso questa estrazione è stata il punto di partenza per recuperare i blocchi che non potevamo ottenere correttamente dal `BBLOCKS.CCF` danneggiato.

### Preparazione della nuova immagine PC1

Il nuovo `BBLOCKS.CCF` viene invece costruito partendo da un'immagine logica **160×200 a 16 colori**.

Per il builder sono importanti gli **indici della palette**, non soltanto l'aspetto visivo dei colori. Se non si è certi che il PNG sorgente utilizzi già esattamente la palette indicizzata richiesta, è quindi consigliabile normalizzarlo:

```bat
py make_indexed_precise.py BBLOCKS_160x200.png BBLOCKS_160x200_INDEXED.png
```

Il file ottenuto deve essere un PNG palettizzato i cui pixel utilizzano gli indici 0..15 previsti dal progetto.

### Costruzione del nuovo BBLOCKS.CCF

A questo punto il file PC1 può essere costruito con:

```bat
py bb_build_bblocks_pc1.py BBLOCKS_160x200_INDEXED.png --out build\BBLOCKS.CCF
```

Per conservare anche il raw generato e una preview:

```bat
py bb_build_bblocks_pc1.py BBLOCKS_160x200_INDEXED.png --out build\BBLOCKS.CCF --raw build\BBLOCKS.raw --preview build\BBLOCKS_preview.png
```

Il builder converte l'immagine logica 160×200 nella codifica a doppio pixel utilizzata dalla modalità PC1 e ricomprime il risultato nel formato utilizzato dal gioco.

# Schermate statiche

Oltre agli sprite e ai blocchi dei livelli, Bubble Bobble contiene alcune schermate grafiche memorizzate in file CCF separati. Nel progetto abbiamo lavorato su **TITLEPIC.CCF**, **EXTEND.CCF** e **SECRET.CCF**.

Questi file possono essere trattati con lo stesso gruppo di strumenti, raccolti in `tools/static/`. Il workflow è volutamente simile per tutte e tre le schermate: si estrae il CCF originale in una directory di lavoro, si prepara una nuova immagine logica 160×200 a 16 colori, la si converte nella rappresentazione a doppio pixel richiesta dal PC1 e infine si ricostruisce il CCF conservando la struttura ricavata dal file originale.

La separazione fra **immagine logica 160×200** e **immagine codificata 320×200** è importante. Il file grafico che si disegna o modifica rappresenta ciò che si vuole vedere sul PC1; `bb_pc1_encode_160_to_cga320.py` effettua invece la trasformazione necessaria al formato video utilizzato dal gioco. L'opzione `--preview` permette inoltre di controllare visivamente il risultato della conversione prima della ricostruzione.

### TITLEPIC.CCF

`TITLEPIC.CCF` contiene la schermata principale mostrata dal gioco. Per prima cosa viene estratto il file originale:

```bat
py bb_extract_static_ccf.py TITLEPIC.CCF --out work_titlepic --clean
```

La directory `work_titlepic` conserva la struttura e le informazioni necessarie al successivo rebuild. La nuova schermata viene preparata come immagine 160×200 e convertita nel formato PC1:

```bat
py bb_pc1_encode_160_to_cga320.py TITLEPIC_160x200.png TITLEPIC_pc1.png --preview
```

L'immagine convertita deve quindi sostituire l'immagine `TITLEPIC` corrispondente nella directory di lavoro prodotta dall'estrattore. A quel punto il nuovo CCF può essere ricostruito:

```bat
py bb_build_static_ccf.py work_titlepic --out build\TITLEPIC.CCF
```

### EXTEND.CCF

`EXTEND.CCF` contiene la schermata utilizzata nella sequenza **EXTEND**. Il procedimento è lo stesso: estrazione del file originale, conversione della nuova grafica e ricostruzione.

```bat
py bb_extract_static_ccf.py EXTEND.CCF --out work_extend --clean
py bb_pc1_encode_160_to_cga320.py EXTEND_160x200.png EXTEND_pc1.png --preview
```

L'immagine `EXTEND_pc1.png` deve essere utilizzata come nuova immagine `EXTEND` nella directory `work_extend`. Infine:

```bat
py bb_build_static_ccf.py work_extend --out build\EXTEND.CCF
```

### SECRET.CCF

`SECRET.CCF` viene gestito nello stesso modo. Dopo l'estrazione:

```bat
py bb_extract_static_ccf.py SECRET.CCF --out work_secret --clean
```

si converte la nuova immagine 160×200:

```bat
py bb_pc1_encode_160_to_cga320.py SECRET_160x200.png SECRET_pc1.png --preview
```

`SECRET_pc1.png` viene quindi utilizzata come nuova immagine `SECRET` nella directory `work_secret`, senza alterare gli altri file prodotti dall'estrazione. La ricostruzione finale è:

```bat
py bb_build_static_ccf.py work_secret --out build\SECRET.CCF
```

In tutti e tre i casi il principio è quindi lo stesso: **il CCF originale fornisce la struttura, mentre il PNG 160×200 fornisce la nuova grafica**. Gli strumenti si occupano della codifica PC1 e della ricostruzione del file utilizzabile dal gioco.

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
   └ cheats/
```

# Stato e copyright

Il repository documenta le parti sufficientemente stabili e verificate. Una parte significativa del risultato è stata provata sul vero Olivetti Prodest PC1.

Non vengono distribuiti `BUBBLE.EXE`, `BUBBOB.DAT`, CCF/TCF originali, eseguibili modificati, sprite o altre risorse grafiche originali. Gli strumenti richiedono i file provenienti dalla copia dell'utente.

Bubble Bobble, personaggi, grafica originale, marchi e materiali del gioco appartengono ai rispettivi titolari. Il progetto è indipendente e non è affiliato né approvato da Taito.

Il codice originale, gli strumenti, le patch e la documentazione realizzati specificamente per questo progetto sono distribuiti secondo la **MIT License**; vedere `LICENSE`. La licenza non si applica e non concede alcun diritto sui file, sulla grafica, sui personaggi, sui marchi o su qualsiasi altro materiale appartenente al gioco originale.


---

# English version

# Bubble Bobble PC1 — 16-color edition

## The project

This project was created to adapt the graphics of the 1989 DOS version of **Bubble Bobble** to the unusual video capabilities of the **Olivetti Prodest PC1**, equipped with the Yamaha V6355D video controller.

The original DOS release supports several graphics adapters of the period, including CGA, EGA and Tandy. The Prodest PC1 is CGA-compatible, but it also provides an extended **160×200 16-color** mode that the original game does not use.

The idea behind the project was therefore to find out whether this mode could be exploited to create a graphically richer version of Bubble Bobble on the PC1 while keeping the original structure of the game as intact as possible.

This is neither a remake nor a rewrite of the game.

The work was carried out through reverse engineering of the original DOS version, analysis of its graphics formats, development of tools to extract and rebuild its resources, and a number of targeted patches to the original code. One of the main goals was to alter the original program as little as possible. Wherever possible, changes were limited to the graphics drivers and to the data strictly required by the new PC1 mode.

Another goal was to preserve compatibility with the other original graphics systems. For example, the new `ARCADE.TCF` screen, although redesigned from a 160×200 source, is also displayed correctly through the EGA and Tandy drivers thanks to specific changes to their renderers.

The project is primarily technical, historical and educational: it is an attempt to study how a late-1980s commercial DOS game works and to explore what the Prodest PC1 hardware might have offered if the game had been specifically designed to take advantage of it.

## Authors and contributions

### Massimiliano Pascuzzi

Project concept and coordination, reverse engineering, analysis and testing of the modifications, development of the graphics workflow, and verification on real Olivetti Prodest PC1 hardware.

### Davide Ottonelli

Redesign and adaptation of the game graphics to the horizontally doubled-pixel representation required by the PC1 160×200 16-color mode.

A significant part of the graphics work involved redrawing sprites and game elements while taking into account not only the 16 available colors, but also the unusual pixel geometry of this video mode.

### ChatGPT (OpenAI)

Assistance with reverse engineering, assembly-code and binary-format analysis, development and review of the Python tools, binary-patch design, and technical documentation.

The work was carried out iteratively: code analysis, formulation of modifications, testing under emulation, and verification of the results on real hardware.

### Acknowledgements

Special thanks to the [**rebb64**](https://github.com/zaidka/rebb64) project, which was valuable for studying the graphics of the Commodore 64 version of Bubble Bobble and allowed us to use blocks extracted from that version as a basis for the graphics work.

The original Bubble Bobble graphics and all related rights naturally remain the property of their respective rights holders.

## The PC1 video mode

The project uses an extended mode of the Yamaha V6355D controller providing **160×200 pixels in 16 colors**.

In the graphics representation, each logical 16-color pixel is encoded using two adjacent CGA 2bpp pixels. For a color index `i` from 0 to 15:

```text
left  = (i >> 2) & 3
right = i & 3
```

For example:

```text
color 8  -> (2,0)
color 2  -> (0,2)
color 5  -> (1,1)
color 15 -> (3,3)
```

As a result, a logical image 160 pixels wide is represented by an encoded image 320 pixels wide. This principle is the basis of the conversion tools included in the repository. See `docs/PC1-VIDEO.md` for technical details.

## Original game files involved

The project works with several files from the original DOS version of Bubble Bobble. **None of these original files are distributed in this repository.**

| File | Contents / purpose | Modification |
|---|---|---|
| `BUBBLE.EXE` | loader and video handling | PC1 initialization and renderer patches |
| `BUBBOB.DAT` | main game program | graphics patches and optional modifications |
| `SPRITES.CCF` | game sprites | extraction, redesign, masks, conversion and rebuild |
| `BBLOCKS.CCF` | level graphics | PC1 rebuild |
| `BBLOCKS.TCF` | alternate block graphics | used during development to recover the blocks |
| `TITLEPIC.CCF` | title screen | extraction, conversion and rebuild |
| `EXTEND.CCF` | EXTEND screen | extraction, conversion and rebuild |
| `SECRET.CCF` | SECRET screen | extraction, conversion and rebuild |
| `ARCADE.TCF` | ARCADE screen | 160×200 conversion and renderer adaptation |

### Note about BBLOCKS.TCF

In the copy of the game used during development, `BBLOCKS.CCF` was damaged. For this reason, `BBLOCKS.TCF` was used as an alternative source from which the block graphics could be recovered correctly.

The use of the `.TCF` therefore comes solely from this circumstance; it is not a general requirement for converting `BBLOCKS.CCF`.

# SPRITES.CCF

The dedicated tools are in `tools/sprites/`.

### 1. Extraction

```bat
py bb_extract_sprites_ccf.py SPRITES.CCF --out work_original --clean
```

### 2. Duplicate detection and mega-PNG creation

```bat
py bb_mark_duplicate_sprites.py work_original\sprites
```

This produces:

```text
sprites_duplicates_annotated.png
sprites_duplicates_report.txt
sprites_duplicates.csv
```

During development, **2,848 images** were analyzed, corresponding to **547 unique groups** and **2,301 duplicates**.

### 3. Redesign

The mega-PNG is edited to create the new 16-color graphics. In the following examples the resulting file is called `SPRITES_16_COLOURS.png`.

### 4. Reimport

```bat
py bb_import_edited_sprite_sheet.py SPRITES_16_COLOURS.png work_original\sprites sprites_duplicates.csv work_edited\sprites --clean
```

### 5. Preparing the PC1 directory

The final directory must also contain `manifest.json` and `source\` from the original extraction:

```bat
copy work_original\manifest.json work_pc1\manifest.json
xcopy work_original\source work_pc1\source /E /I /Y
```

### 6. Converting the sprites to PC1 format

```bat
py bb_convert_sprite16_to_pc1.py work_edited\sprites work_pc1\sprites
```

**Convert only the sprite graphics, not the masks.** Conversion must be performed **before** the final masks are added.

```text
sprite reimport -> PC1 conversion -> mask merge -> build
```

### 7. Masks

The masks were obtained from a second mega-PNG in which black areas that genuinely belong to the sprites are temporarily changed to a non-black color. This makes it possible to distinguish the black background, which represents transparency, from opaque black areas that are part of the sprite itself.

### 8. Merging the masks

Only after the PC1 conversion:

```bat
robocopy work_masks\sprites work_pc1\sprites phase_*_mask.png /S
```

After this merge, **do not run the PC1 conversion again** on the resulting directory.

### 9. Rebuild

```bat
py bb_build_sprites_ccf.py work_pc1 --import-masks --out build\SPRITES.CCF
```

# BBLOCKS.CCF

`BBLOCKS.CCF` contains the graphics used to construct the game levels. The dedicated tools are in `tools/bblocks/`.

As explained above, this project used `BBLOCKS.TCF` as a source only because the `BBLOCKS.CCF` in our copy of the game was damaged. The repository therefore also includes a tool for extracting and viewing the graphics contained in the TCF.

### Extracting the blocks from BBLOCKS.TCF

Starting from the original file:

```bat
py bb_extract_bblocks_tcf.py BBLOCKS.TCF --out work_bblocks_tcf --clean
```

The script decompresses the Bubble LZW stream and creates a working directory containing the extracted PNG and the data used to document the operation:

```text
work_bblocks_tcf\
    manifest.json
    source\
        BBLOCKS.TCF.original
        BBLOCKS.TCF.raw
        BBLOCKS.image_32000.raw
        BBLOCKS.tail.bin
    image\
        BBLOCKS.png
```

`BBLOCKS.png` represents the graphics extracted from the TCF as an indexed **320×200 16-color** image. The first 32,000 decompressed bytes are interpreted as packed 4bpp graphics, with the high nibble representing the left pixel and the low nibble the right pixel. Any following bytes are preserved separately in `BBLOCKS.tail.bin`.

In our case, this extraction was the starting point for recovering the blocks that could not be obtained correctly from the damaged `BBLOCKS.CCF`.

### Preparing the new PC1 image

The new `BBLOCKS.CCF` is instead built from a logical **160×200 16-color** image.

The builder depends on **palette indices**, not merely on the visible RGB colors. If there is any doubt that the source PNG already uses exactly the required indexed palette, it is therefore advisable to normalize it first:

```bat
py make_indexed_precise.py BBLOCKS_160x200.png BBLOCKS_160x200_INDEXED.png
```

The resulting file must be a paletted PNG whose pixels use the 0..15 indices expected by the project.

### Building the new BBLOCKS.CCF

The PC1 file can then be built with:

```bat
py bb_build_bblocks_pc1.py BBLOCKS_160x200_INDEXED.png --out build\BBLOCKS.CCF
```

To also save the generated raw data and a preview:

```bat
py bb_build_bblocks_pc1.py BBLOCKS_160x200_INDEXED.png --out build\BBLOCKS.CCF --raw build\BBLOCKS.raw --preview build\BBLOCKS_preview.png
```

The builder converts the logical 160×200 image into the doubled-pixel encoding used by the PC1 mode and recompresses the result into the format used by the game.

# Static screens

In addition to sprites and level blocks, Bubble Bobble contains several graphics screens stored in separate CCF files. This project works with **TITLEPIC.CCF**, **EXTEND.CCF**, and **SECRET.CCF**.

These files can all be handled with the same set of tools in `tools/static/`. The workflow is deliberately similar for all three screens: extract the original CCF into a working directory, prepare a new logical 160×200 16-color image, convert it to the doubled-pixel representation required by the PC1, and finally rebuild the CCF while preserving the structure recovered from the original file.

The distinction between the **logical 160×200 image** and the **encoded 320×200 image** is important. The image that is drawn or edited represents what should appear on the PC1; `bb_pc1_encode_160_to_cga320.py` performs the transformation required by the video representation used by the game. The `--preview` option also makes it possible to inspect the conversion result before rebuilding the file.

### TITLEPIC.CCF

`TITLEPIC.CCF` contains the game's main title screen. First extract the original file:

```bat
py bb_extract_static_ccf.py TITLEPIC.CCF --out work_titlepic --clean
```

The `work_titlepic` directory preserves the structure and information required for the later rebuild. Prepare the new screen as a 160×200 image and convert it to PC1 format:

```bat
py bb_pc1_encode_160_to_cga320.py TITLEPIC_160x200.png TITLEPIC_pc1.png --preview
```

The converted image must then replace the corresponding `TITLEPIC` image in the working directory produced by the extractor. The new CCF can then be rebuilt:

```bat
py bb_build_static_ccf.py work_titlepic --out build\TITLEPIC.CCF
```

### EXTEND.CCF

`EXTEND.CCF` contains the screen used in the **EXTEND** sequence. The procedure is the same: extract the original file, convert the new graphics, and rebuild it.

```bat
py bb_extract_static_ccf.py EXTEND.CCF --out work_extend --clean
py bb_pc1_encode_160_to_cga320.py EXTEND_160x200.png EXTEND_pc1.png --preview
```

Use `EXTEND_pc1.png` as the new `EXTEND` image in the `work_extend` directory. Finally:

```bat
py bb_build_static_ccf.py work_extend --out build\EXTEND.CCF
```

### SECRET.CCF

`SECRET.CCF` is handled in the same way. After extraction:

```bat
py bb_extract_static_ccf.py SECRET.CCF --out work_secret --clean
```

convert the new 160×200 image:

```bat
py bb_pc1_encode_160_to_cga320.py SECRET_160x200.png SECRET_pc1.png --preview
```

Use `SECRET_pc1.png` as the new `SECRET` image in `work_secret`, without altering the other files generated during extraction. The final rebuild is:

```bat
py bb_build_static_ccf.py work_secret --out build\SECRET.CCF
```

For all three screens the principle is the same: **the original CCF provides the structure, while the 160×200 PNG provides the new graphics**. The tools handle the PC1 encoding and reconstruction of a file usable by the game.

# ARCADE.TCF

The dedicated tools are in `tools/arcade/`.

```bat
py bb_extract_arcade_tcf.py ARCADE.TCF --out work_arcade --clean
```

Extraction produces `work_arcade\image\ARCADE.png` at 320×200. Replace it with the new **160×200 16-color** image, keeping the filename `ARCADE.png`.

```bat
py bb_build_arcade_tcf_pc1.py work_arcade --out build\ARCADE.TCF
```

The builder converts the PNG to packed 4bpp, preserves the original tail data, recompresses the contents, and automatically verifies the result by decompressing it again. The new graphics section occupies 16,000 decompressed bytes.

The change in width required adaptations to the **PC1, EGA and Tandy** renderers. Patch details and exact bytes are documented in `patches/BUBBLE-EXE.md`.

# BUBBLE.EXE

The patches cover PC1 initialization and the PC1/EGA/Tandy renderers. See `patches/BUBBLE-EXE.md`. The repository distributes neither the original nor a modified executable.

# BUBBOB.DAT

`BUBBOB.DAT` is an EXEPACK-compressed DOS executable. For static analysis:

```bat
py unexepack_py.py BUBBOB.DAT BUBBOB_UNPACKED.EXE
```

The unpacked file is intended only for IDA/static analysis; the game continues to use `BUBBOB.DAT` at runtime. Verified patches are documented in `patches/BUBBOB-DAT.md`.

# BBCHEAT.COM

`tools/cheats/BBCHEAT.ASM` is an 8086/DOS utility used to enable or disable invulnerability and to select the initial level from 1 to 100. It validates the expected bytes before modifying them. It was assembled and tested with **TASM 1.0**.

# Requirements

- Python 3
- Pillow
- your own compatible copy of the DOS version of Bubble Bobble

```bat
pip install -r requirements.txt
```

# Repository structure

```text
bubble-bobble-pc1/
├ README.md
├ LICENSE
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
   └ cheats/
```

# Project status and copyright

The repository documents the parts of the project that have reached a sufficiently stable and verified state. A significant part of the final result has also been tested directly on a real Olivetti Prodest PC1.

The repository does not distribute `BUBBLE.EXE`, `BUBBOB.DAT`, original CCF/TCF files, modified game executables, sprites, or other original graphics assets. The tools require files supplied by the user from their own copy of the game.

Bubble Bobble, its characters, original graphics, trademarks, and other original game materials remain the property of their respective rights holders. This project is independent and is not affiliated with or endorsed by Taito.

The original code, tools, patches, and documentation created specifically for this project are distributed under the **MIT License**; see `LICENSE`. The license does not apply to, and grants no rights over, files, graphics, characters, trademarks, or any other material belonging to the original game.
