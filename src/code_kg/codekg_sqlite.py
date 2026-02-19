#!/usr/bin/env python3
"""
codekg_sqlite.py

SQLite persistence layer for the Code Knowledge Graph.

SQLite is the authoritative store:
- nodes table
- edges table

This module is deterministic and testable.
No embeddings, no LanceDB, no AST.

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Sequence

from code_kg.codekg import Edge, Node

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS nodes (
  id           TEXT PRIMARY KEY,
  kind         TEXT NOT NULL,
  name         TEXT NOT NULL,
  qualname     TEXT,
  module_path  TEXT,
  lineno       INTEGER,
  end_lineno   INTEGER,
  docstring    TEXT
);

CREATE TABLE IF NOT EXISTS edges (
  src      TEXT NOT NULL,
  rel      TEXT NOT NULL,
  dst      TEXT NOT NULL,
  evidence TEXT,
  PRIMARY KEY (src, rel, dst)
);

CREATE INDEX IF NOT EXISTS idx_nodes_kind   ON nodes(kind);
CREATE INDEX IF NOT EXISTS idx_nodes_name   ON nodes(name);
CREATE INDEX IF NOT EXISTS idx_nodes_module ON nodes(module_path);

CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);
CREATE INDEX IF NOT EXISTS idx_edges_rel ON edges(rel);
"""


def connect_sqlite(db_path: Path) -> sqlite3.Connection:
    """
    Connect to SQLite and ensure schema exists.

    :param db_path: Path to sqlite database file
    :return: sqlite3 connection
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.executescript(SCHEMA_SQL)
    return con


def clear_graph(con: sqlite3.Connection) -> None:
    """
    Delete all nodes and edges.

    :param con: sqlite3 connection
    """
    con.execute("DELETE FROM edges;")
    con.execute("DELETE FROM nodes;")
    con.commit()


def upsert_nodes(con: sqlite3.Connection, nodes: Iterable[Node]) -> int:
    """
    Insert/update nodes.

    :param con: sqlite3 connection
    :param nodes: iterable of Node
    :return: number of rows affected (best-effort)
    """
    rows = [
        (
            n.id,
            n.kind,
            n.name,
            n.qualname,
            n.module_path,
            n.lineno,
            n.end_lineno,
            n.docstring,
        )
        for n in nodes
    ]

    con.executemany(
        """
        INSERT INTO nodes (id, kind, name, qualname, module_path, lineno, end_lineno, docstring)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            kind=excluded.kind,
            name=excluded.name,
            qualname=excluded.qualname,
            module_path=excluded.module_path,
            lineno=excluded.lineno,
            end_lineno=excluded.end_lineno,
            docstring=excluded.docstring
        """,
        rows,
    )
    con.commit()
    return con.total_changes


def upsert_edges(con: sqlite3.Connection, edges: Iterable[Edge]) -> int:
    """
    Insert/update edges.

    :param con: sqlite3 connection
    :param edges: iterable of Edge
    :return: number of rows affected (best-effort)
    """
    rows = [
        (
            e.src,
            e.rel,
            e.dst,
            (
                json.dumps(e.evidence, ensure_ascii=False)
                if e.evidence is not None
                else None
            ),
        )
        for e in edges
    ]

    con.executemany(
        """
        INSERT INTO edges (src, rel, dst, evidence)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(src, rel, dst) DO UPDATE SET
            evidence=excluded.evidence
        """,
        rows,
    )
    con.commit()
    return con.total_changes


def write_graph(
    con: sqlite3.Connection,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    *,
    wipe: bool = False,
) -> None:
    """
    Persist a whole graph to SQLite.

    :param con: sqlite3 connection
    :param nodes: nodes list
    :param edges: edges list
    :param wipe: if True, clears existing graph before writing
    """
    if wipe:
        clear_graph(con)
    upsert_nodes(con, nodes)
    upsert_edges(con, edges)
