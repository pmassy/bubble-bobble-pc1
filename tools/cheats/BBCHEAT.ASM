; ------------------------------------------------------------
; BBCHEAT.ASM
; Bubble Bobble PC1 - Debug Cheat
;
; Invulnerabilita':
;   BUBBOB.DAT offset 944Dh
;   72h = normale
;   EBh = invulnerabile
;
; Livello iniziale:
;   BUBBOB.DAT offset 0523h (word little-endian)
;   FFFFh = livello 1
;   0000h = livello 2
;   ...
;   0062h = livello 100
;
; 8086 / DOS .COM
; TASM 3.1 compatible
; ------------------------------------------------------------

.model tiny
.code
org 100h

INV_PATCH_OFFSET   equ 944Dh
LEVEL_PATCH_OFFSET equ 0523h
NORMAL_BYTE        equ 72h
INVULN_BYTE        equ 0EBh

start:

    push cs
    pop  ds

    ; --------------------------------------------------------
    ; Apri BUBBOB.DAT read/write
    ; --------------------------------------------------------

    mov dx, offset filename
    mov ax, 3D02h
    int 21h

    jnc OpenOK
    jmp OpenError

OpenOK:
    mov [handle], ax

    ; --------------------------------------------------------
    ; Leggi stato invulnerabilita'
    ; --------------------------------------------------------

    mov bx, [handle]
    call SeekInvPatch

    jnc InvSeekOK
    jmp SeekError

InvSeekOK:
    mov ah, 3Fh
    mov cx, 1
    mov dx, offset currentByte
    int 21h

    jnc InvReadOK1
    jmp ReadError

InvReadOK1:
    cmp ax, 1
    je InvReadOK2
    jmp ReadError

InvReadOK2:
    mov al, [currentByte]

    cmp al, NORMAL_BYTE
    je InvByteOK

    cmp al, INVULN_BYTE
    je InvByteOK

    mov dx, offset msgUnexpectedInv
    call PrintString
    jmp CloseAndExit

InvByteOK:

    ; --------------------------------------------------------
    ; Leggi livello iniziale
    ; --------------------------------------------------------

    mov bx, [handle]
    call SeekLevelPatch

    jnc LevelSeekOK
    jmp SeekError

LevelSeekOK:
    mov ah, 3Fh
    mov cx, 2
    mov dx, offset levelWord
    int 21h

    jnc LevelReadOK1
    jmp ReadError

LevelReadOK1:
    cmp ax, 2
    je LevelReadOK2
    jmp ReadError

LevelReadOK2:
    mov ax, [levelWord]

    cmp ax, 0FFFFh
    je LevelIsOne

    cmp ax, 62h
    jbe LevelIsNormal

    mov dx, offset msgUnexpectedLevel
    call PrintString
    jmp CloseAndExit

LevelIsOne:
    mov word ptr [displayLevel], 1
    jmp ShowStatus

LevelIsNormal:
    add ax, 2
    mov [displayLevel], ax


; ------------------------------------------------------------
; Stato + menu principale
; ------------------------------------------------------------

ShowStatus:

    mov dx, offset msgTitle
    call PrintString

    mov al, [currentByte]
    cmp al, INVULN_BYTE
    je StatusInvOn

    mov dx, offset msgNormal
    call PrintString
    jmp StatusLevel

StatusInvOn:
    mov dx, offset msgInvuln
    call PrintString

StatusLevel:
    mov dx, offset msgLevelCurrent
    call PrintString

    mov ax, [displayLevel]
    call PrintNumber

    mov dx, offset msgCRLF
    call PrintString

    mov dx, offset msgMenu
    call PrintString

    ; Buffered input: consuma anche ENTER
    mov dx, offset menuInput
    mov ah, 0Ah
    int 21h

    cmp byte ptr [menuInput+1], 1
    je MenuCountOK

    mov dx, offset msgInvalidMenu
    call PrintString
    jmp ShowStatus

MenuCountOK:
    mov al, [menuInput+2]

    cmp al, '1'
    jne MenuNot1
    jmp ChoiceEnable
MenuNot1:

    cmp al, '2'
    jne MenuNot2
    jmp ChoiceDisable
MenuNot2:

    cmp al, '3'
    jne MenuNot3
    jmp ChoiceLevel
MenuNot3:

    cmp al, '0'
    jne MenuBadChoice
    jmp ChoiceExit
MenuBadChoice:

    mov dx, offset msgInvalidMenu
    call PrintString
    jmp ShowStatus


; ------------------------------------------------------------
; Invulnerabilita' ON/OFF
; ------------------------------------------------------------

ChoiceEnable:
    mov byte ptr [newByte], INVULN_BYTE
    call WriteInvPatch

    jnc EnableOK
    jmp WriteError

EnableOK:
    mov byte ptr [currentByte], INVULN_BYTE
    mov dx, offset msgEnabled
    call PrintString
    jmp ShowStatus


ChoiceDisable:
    mov byte ptr [newByte], NORMAL_BYTE
    call WriteInvPatch

    jnc DisableOK
    jmp WriteError

DisableOK:
    mov byte ptr [currentByte], NORMAL_BYTE
    mov dx, offset msgDisabled
    call PrintString
    jmp ShowStatus


; ------------------------------------------------------------
; Impostazione livello iniziale
; ------------------------------------------------------------

ChoiceLevel:

    mov dx, offset msgAskLevel
    call PrintString

    mov dx, offset levelInput
    mov ah, 0Ah
    int 21h

    ; Nessun carattere = errore
    mov cl, [levelInput+1]
    xor ch, ch
    jcxz LevelInputEmpty
    jmp LevelInputPresent

LevelInputEmpty:
    jmp BadLevel

LevelInputPresent:
    mov si, offset levelInput+2
    xor ax, ax

ParseLevelLoop:

    mov dl, [si]

    cmp dl, '0'
    jnb DigitAbove0
    jmp BadLevel
DigitAbove0:

    cmp dl, '9'
    jbe DigitValid
    jmp BadLevel
DigitValid:

    sub dl, '0'
    xor dh, dh
    push dx

    mov bx, 10
    mul bx

    pop dx
    add ax, dx

    inc si
    loop ParseLevelLoop

    ; 0 = lascia invariato
    cmp ax, 0
    jne LevelNotZero
    jmp LevelNoChange

LevelNotZero:
    cmp ax, 100
    jbe LevelRangeOK
    jmp BadLevel

LevelRangeOK:

    mov [displayLevel], ax

    cmp ax, 1
    je BuildLevelOne

    sub ax, 2
    mov [newLevelWord], ax
    jmp WriteLevelPatch

BuildLevelOne:
    mov word ptr [newLevelWord], 0FFFFh

WriteLevelPatch:

    mov bx, [handle]
    call SeekLevelPatch

    jnc LevelWriteSeekOK
    jmp SeekError

LevelWriteSeekOK:
    mov ah, 40h
    mov cx, 2
    mov dx, offset newLevelWord
    int 21h

    jnc LevelWriteOK1
    jmp WriteError

LevelWriteOK1:
    cmp ax, 2
    je LevelWriteOK2
    jmp WriteError

LevelWriteOK2:
    mov ax, [newLevelWord]
    mov [levelWord], ax

    mov dx, offset msgLevelSet
    call PrintString

    mov ax, [displayLevel]
    call PrintNumber

    mov dx, offset msgCRLF
    call PrintString
    jmp ShowStatus


BadLevel:
    mov dx, offset msgBadLevel
    call PrintString
    jmp ChoiceLevel


LevelNoChange:
    mov dx, offset msgNoChange
    call PrintString
    jmp ShowStatus


ChoiceExit:
    mov dx, offset msgBye
    call PrintString
    jmp CloseAndExit


; ------------------------------------------------------------
; WriteInvPatch
; Scrive newByte a 944Dh
; ritorno CF=0 OK / CF=1 errore
; ------------------------------------------------------------

WriteInvPatch proc near

    push ax
    push bx
    push cx
    push dx

    mov bx, [handle]
    call SeekInvPatch
    jc  WIP_Error

    mov ah, 40h
    mov cx, 1
    mov dx, offset newByte
    int 21h
    jc  WIP_Error

    cmp ax, 1
    jne WIP_Error

    clc
    jmp short WIP_Done

WIP_Error:
    stc

WIP_Done:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

WriteInvPatch endp


; ------------------------------------------------------------
; Errori
; ------------------------------------------------------------

OpenError:
    mov dx, offset msgOpenError
    call PrintString
    jmp ExitProgram

SeekError:
    mov dx, offset msgSeekError
    call PrintString
    jmp CloseAndExit

ReadError:
    mov dx, offset msgReadError
    call PrintString
    jmp CloseAndExit

WriteError:
    mov dx, offset msgWriteError
    call PrintString
    jmp CloseAndExit


; ------------------------------------------------------------
; Chiudi file
; ------------------------------------------------------------

CloseAndExit:
    mov bx, [handle]
    mov ah, 3Eh
    int 21h

ExitProgram:
    mov ax, 4C00h
    int 21h


; ------------------------------------------------------------
; SeekInvPatch
; BX = handle
; ------------------------------------------------------------

SeekInvPatch proc near

    mov ax, 4200h
    xor cx, cx
    mov dx, INV_PATCH_OFFSET
    int 21h
    ret

SeekInvPatch endp


; ------------------------------------------------------------
; SeekLevelPatch
; BX = handle
; ------------------------------------------------------------

SeekLevelPatch proc near

    mov ax, 4200h
    xor cx, cx
    mov dx, LEVEL_PATCH_OFFSET
    int 21h
    ret

SeekLevelPatch endp


; ------------------------------------------------------------
; PrintString
; DS:DX = string terminata da $
; ------------------------------------------------------------

PrintString proc near

    mov ah, 09h
    int 21h
    ret

PrintString endp


; ------------------------------------------------------------
; PrintNumber
; AX = numero unsigned da stampare in decimale
; ------------------------------------------------------------

PrintNumber proc near

    push ax
    push bx
    push cx
    push dx

    xor cx, cx
    mov bx, 10

PN_Divide:
    xor dx, dx
    div bx
    push dx
    inc cx
    or ax, ax
    jnz PN_Divide

PN_Print:
    pop dx
    add dl, '0'
    mov ah, 02h
    int 21h
    loop PN_Print

    pop dx
    pop cx
    pop bx
    pop ax
    ret

PrintNumber endp


; ------------------------------------------------------------
; Dati
; ------------------------------------------------------------

filename        db 'BUBBOB.DAT',0

handle          dw 0
currentByte     db 0
newByte         db 0
levelWord       dw 0
newLevelWord    dw 0
displayLevel    dw 1

; DOS AH=0Ah input buffers
menuInput       db 2,0,3 dup(0)
levelInput      db 4,0,5 dup(0)

msgTitle        db 13,10
                db 'Bubble Bobble PC1 - Debug Cheat',13,10
                db '--------------------------------',13,10,'$'

msgNormal       db 'Invulnerabilita'' attuale: DISATTIVATA',13,10,'$'
msgInvuln       db 'Invulnerabilita'' attuale: ATTIVA',13,10,'$'

msgLevelCurrent db 'Livello iniziale: $'

msgMenu         db 13,10
                db '1 - Attiva invulnerabilita''',13,10
                db '2 - Disattiva invulnerabilita''',13,10
                db '3 - Imposta livello iniziale',13,10
                db '0 - Esci',13,10,13,10
                db 'Scelta: $'

msgAskLevel     db 13,10
                db 'Livello iniziale (1-100, 0 = invariato): $'

msgEnabled      db 13,10
                db 'Invulnerabilita'' ATTIVATA.',13,10,'$'

msgDisabled     db 13,10
                db 'Invulnerabilita'' DISATTIVATA.',13,10,'$'

msgLevelSet     db 13,10
                db 'Livello iniziale impostato a: $'

msgNoChange     db 13,10
                db 'Nessuna modifica effettuata.',13,10,'$'

msgInvalidMenu  db 13,10
                db 'Scelta non valida.',13,10,'$'

msgBadLevel     db 13,10
                db 'Valore non valido. Inserire un numero da 1 a 100',13,10
                db 'oppure 0 per lasciare il valore invariato.',13,10,'$'

msgUnexpectedInv db 13,10
                 db 'ERRORE: byte inatteso a offset 944Dh.',13,10
                 db 'Attesi 72h oppure EBh.',13,10
                 db 'Nessuna modifica effettuata.',13,10,'$'

msgUnexpectedLevel db 13,10
                   db 'ERRORE: valore inatteso a offset 0523h.',13,10
                   db 'Atteso FFFFh oppure un valore da 0000h a 0062h.',13,10
                   db 'Nessuna modifica effettuata.',13,10,'$'

msgOpenError    db 13,10
                db 'ERRORE: impossibile aprire BUBBOB.DAT.',13,10,'$'

msgSeekError    db 13,10
                db 'ERRORE durante il posizionamento nel file.',13,10,'$'

msgReadError    db 13,10
                db 'ERRORE durante la lettura di BUBBOB.DAT.',13,10,'$'

msgWriteError   db 13,10
                db 'ERRORE durante la scrittura di BUBBOB.DAT.',13,10,'$'

msgBye          db 13,10
                db 'Uscita senza altre modifiche.',13,10,'$'

msgCRLF         db 13,10,'$'

end start
