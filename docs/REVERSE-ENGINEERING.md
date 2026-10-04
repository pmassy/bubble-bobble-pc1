# Reverse-engineering notes

## BUBBOB.DAT and IDA

`BUBBOB.DAT` is an EXEPACK-packed DOS executable/module. The project uses `tools/ida/unexepack_py.py` to create an unpacked EXE suitable for static analysis:

```bat
py tools\ida\unexepack_py.py BUBBOB.DAT BUBBOB_UNPACKED.EXE
```

Do not run the unpacker on `BUBBLE.EXE`; the project established that `BUBBLE.EXE` is not EXEPACK-packed.

The unpacked output is an analysis artifact only. Runtime patches are applied to the actual game files and therefore require careful offset translation and verification.

## Scope

Only findings that reached a verified working state are documented in the main repository.
