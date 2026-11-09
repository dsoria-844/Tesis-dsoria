"""Lectura incremental de cowrie.json con offsets persistentes (TS-103).

Maneja: archivo todavía inexistente, líneas parciales (se espera al salto de línea),
truncado y rotación diaria (Cowrie renombra cowrie.json -> cowrie.json.AAAA-MM-DD y crea
uno nuevo: se termina de leer el archivo viejo, ubicado por inode, antes de pasar al nuevo).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .ingest import Checkpoint

MAX_READ_BYTES = 4 * 1024 * 1024


@dataclass
class Batch:
    lines: list[str]
    checkpoint: Checkpoint | None   # a confirmar junto con el lote
    more: bool                      # quedan datos por leer ya mismo


class LogTailer:
    def __init__(self, directory: str | Path, name: str, max_lines: int = 500):
        self.dir = Path(directory)
        self.name = name
        self.max_lines = max_lines

    @property
    def path(self) -> Path:
        return self.dir / self.name

    def _find_by_inode(self, inode: int) -> Path | None:
        for cand in sorted(self.dir.glob(self.name + "*")):
            try:
                if cand.stat().st_ino == inode:
                    return cand
            except FileNotFoundError:
                continue
        return None

    def read_batch(self, ck: Checkpoint | None) -> Batch:
        try:
            st = self.path.stat()
        except FileNotFoundError:
            return Batch([], ck, False)

        if ck is None:
            ck = Checkpoint(self.name, st.st_ino, 0)

        if st.st_ino != ck.inode:
            # rotación: terminar el archivo anterior (si todavía existe) y recién después pasar al nuevo
            old = self._find_by_inode(ck.inode)
            if old is not None and old.stat().st_size > ck.offset:
                return self._read(old, ck, rotated=True)
            ck = Checkpoint(self.name, st.st_ino, 0)
            return Batch([], ck, True)

        if st.st_size < ck.offset:  # truncado
            ck = Checkpoint(self.name, st.st_ino, 0)
        if st.st_size == ck.offset:
            return Batch([], ck, False)
        return self._read(self.path, ck, rotated=False)

    def _read(self, path: Path, ck: Checkpoint, rotated: bool) -> Batch:
        with open(path, "rb") as fh:
            fh.seek(ck.offset)
            chunk = fh.read(MAX_READ_BYTES)
        end = chunk.rfind(b"\n")
        if end < 0:  # todavía no hay una línea completa
            return Batch([], ck, False)
        raw_lines = chunk[: end + 1].split(b"\n")[:-1]
        taken = raw_lines[: self.max_lines]
        consumed = sum(len(x) + 1 for x in taken)
        new_ck = Checkpoint(ck.archivo, ck.inode, ck.offset + consumed)
        total = os.stat(path).st_size
        more = len(taken) < len(raw_lines) or (new_ck.offset < total) or rotated
        return Batch([x.decode("utf-8", "replace") for x in taken], new_ck, more)
