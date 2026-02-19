#!/usr/bin/env python3
"""
codekg_lancedb_v0.py

Derived semantic index for the v0 Code Knowledge Graph.

Reads nodes from SQLite and writes vectors to LanceDB.
SQLite remains authoritative; LanceDB is disposable.

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import lancedb
import numpy as np

# -----------------------------
# Embedding backend (pluggable)
# -----------------------------


class Embedder:
    """
    Embedder interface.

    Implement embed_texts(texts) -> list[list[float]]
    """

    dim: int

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class SentenceTransformerEmbedder(Embedder):
    """
    Local embedding via sentence-transformers.

    pip install sentence-transformers
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer  # local import

        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        vecs = self.model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        # ensure float32 lists for LanceDB
        return [np.asarray(v, dtype="float32").tolist() for v in vecs]


# -----------------------------
# Data access
# -----------------------------


@dataclass(frozen=True)
class KgNodeRow:
    id: str
    kind: str
    name: str
    qualname: Optional[str]
    module_path: Optional[str]
    lineno: Optional[int]
    end_lineno: Optional[int]
    docstring: Optional[str]


def read_nodes_from_sqlite(
    sqlite_path: Path,
    *,
    include_kinds: Sequence[str] = ("module", "class", "function", "method"),
) -> List[KgNodeRow]:
    """
    Read nodes from SQLite.

    :param sqlite_path: path to codekg sqlite
    :param include_kinds: which node kinds to index
    """
    con = sqlite3.connect(str(sqlite_path))
    qmarks = ",".join(["?"] * len(include_kinds))
    rows = con.execute(
        f"""
        SELECT id, kind, name, qualname, module_path, lineno, end_lineno, docstring
        FROM nodes
        WHERE kind IN ({qmarks})
        """,
        list(include_kinds),
    ).fetchall()
    con.close()

    return [
        KgNodeRow(
            id=r[0],
            kind=r[1],
            name=r[2],
            qualname=r[3],
            module_path=r[4],
            lineno=r[5],
            end_lineno=r[6],
            docstring=r[7],
        )
        for r in rows
    ]


# -----------------------------
# Index document construction
# -----------------------------


def build_index_text(n: KgNodeRow) -> str:
    """
    Canonical text document used for embedding.

    Keep this stable; it controls semantic behavior.

    :param n: KG node row
    :return: string to embed
    """
    parts = []
    parts.append(f"KIND: {n.kind}")
    parts.append(f"NAME: {n.name}")
    if n.qualname:
        parts.append(f"QUALNAME: {n.qualname}")
    if n.module_path:
        parts.append(f"MODULE: {n.module_path}")
    if n.lineno is not None:
        parts.append(f"LINE: {n.lineno}")
    if n.docstring:
        parts.append("DOCSTRING:\n" + n.docstring.strip())
    return "\n".join(parts)


# -----------------------------
# LanceDB
# -----------------------------


def open_lancedb_table(db_dir: Path, table_name: str, dim: int):
    """
    Open/create a LanceDB table with a stable schema.

    :param db_dir: lancedb directory
    :param table_name: table name
    :param dim: embedding dimension
    :return: LanceDB table
    """
    db_dir.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(db_dir))

    if table_name in db.table_names():
        return db.open_table(table_name)

    dummy = {
        "id": "__dummy__",
        "kind": "dummy",
        "name": "__dummy__",
        "qualname": "",
        "module_path": "",
        "text": "__dummy__",
        "vector": np.zeros((dim,), dtype="float32").tolist(),
    }
    tbl = db.create_table(table_name, data=[dummy])
    tbl.delete("id = '__dummy__'")
    return tbl


def rebuild_lancedb_index(
    sqlite_path: Path,
    lancedb_dir: Path,
    table_name: str,
    embedder: Embedder,
    *,
    include_kinds: Sequence[str] = ("module", "class", "function", "method"),
    wipe: bool = False,
    batch_size: int = 256,
) -> dict:
    """
    Build/rebuild the LanceDB index from SQLite.

    :param sqlite_path: sqlite db path
    :param lancedb_dir: lancedb directory
    :param table_name: lancedb table name
    :param embedder: embedding backend
    :param include_kinds: which nodes to embed
    :param wipe: if True, delete all existing rows first
    :param batch_size: embedding batch size
    :return: stats dict
    """
    nodes = read_nodes_from_sqlite(sqlite_path, include_kinds=include_kinds)
    tbl = open_lancedb_table(lancedb_dir, table_name, embedder.dim)

    if wipe:
        # wipe everything (fast, deterministic)
        tbl.delete("id != ''")  # deletes all rows

    # upsert: delete IDs then add
    indexed = 0
    for i in range(0, len(nodes), batch_size):
        chunk = nodes[i : i + batch_size]
        texts = [build_index_text(n) for n in chunk]
        vecs = embedder.embed_texts(texts)

        ids = [n.id for n in chunk]
        if ids:
            pred = " OR ".join([f"id = '{_escape_sql(nid)}'" for nid in ids])
            tbl.delete(pred)

        rows = []
        for n, text, vec in zip(chunk, texts, vecs):
            rows.append(
                {
                    "id": n.id,
                    "kind": n.kind,
                    "name": n.name,
                    "qualname": n.qualname or "",
                    "module_path": n.module_path or "",
                    "text": text,
                    "vector": vec,
                }
            )
        tbl.add(rows)
        indexed += len(rows)

    return {
        "indexed_rows": indexed,
        "table": table_name,
        "lancedb_dir": str(lancedb_dir),
        "kinds": list(include_kinds),
        "dim": embedder.dim,
    }


def _escape_sql(s: str) -> str:
    # LanceDB delete predicate uses SQL-ish strings; escape single quotes.
    return s.replace("'", "''")
