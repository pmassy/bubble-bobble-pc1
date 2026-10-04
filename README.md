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
