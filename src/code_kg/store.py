#!/usr/bin/env python3
"""
store.py

GraphStore — SQLite persistence layer for the Code Knowledge Graph.

SQLite is the authoritative, canonical store.
No embeddings, no LanceDB, no AST.

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from code_kg.codekg import Edge, Node

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
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

# Default edge types used for graph expansion
DEFAULT_RELS: Tuple[str, ...] = ("CONTAINS", "CALLS", "IMPORTS", "INHERITS")


# ---------------------------------------------------------------------------
# Provenance metadata returned by expand()
# ---------------------------------------------------------------------------


class ProvMeta:
    """
    Provenance metadata for a node returned by :meth:`GraphStore.expand`.

    :param best_hop: Minimum hop distance from any seed node.
    :param via_seed: ID of the seed node that yielded the shortest path.
    """

    __slots__ = ("best_hop", "via_seed")

    def __init__(self, best_hop: int, via_seed: str) -> None:
        self.best_hop = best_hop
        self.via_seed = via_seed

    def __repr__(self) -> str:
        return f"ProvMeta(best_hop={self.best_hop}, via_seed={self.via_seed!r})"


# ---------------------------------------------------------------------------
# GraphStore
# ---------------------------------------------------------------------------


class GraphStore:
    """
    SQLite-backed authoritative store for the Code Knowledge Graph.

    Manages the ``nodes`` and ``edges`` tables and provides graph
    traversal primitives used by the query layer.

    Example::

        store = GraphStore("codekg.sqlite")
        store.write(nodes, edges, wipe=True)
        print(store.stats())

        # fetch a single node
        n = store.node("fn:src/foo.py:bar")

        # expand from seeds
        meta = store.expand({"fn:src/foo.py:bar"}, hop=2)

    :param db_path: Path to the SQLite database file (created if absent).
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._con: Optional[sqlite3.Connection] = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    @property
    def con(self) -> sqlite3.Connection:
        """Lazy SQLite connection (created on first access)."""
        if self._con is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._con = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,  # safe: GraphStore is read-heavy; writes are serialised by SQLite WAL
            )
            self._con.executescript(_SCHEMA_SQL)
        return self._con

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        if self._con is not None:
            self._con.close()
            self._con = None

    def __enter__(self) -> "GraphStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Delete all nodes and edges."""
        self.con.execute("DELETE FROM edges;")
        self.con.execute("DELETE FROM nodes;")
        self.con.commit()

    def write(
        self,
        nodes: Sequence[Node],
        edges: Sequence[Edge],
        *,
        wipe: bool = False,
    ) -> None:
        """
        Persist a complete graph to SQLite.

        :param nodes: Node list from :class:`~code_kg.graph.CodeGraph`.
        :param edges: Edge list from :class:`~code_kg.graph.CodeGraph`.
        :param wipe: If ``True``, clear existing data before writing.
        """
        if wipe:
            self.clear()
        self._upsert_nodes(nodes)
        self._upsert_edges(edges)

    def _upsert_nodes(self, nodes: Iterable[Node]) -> None:
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
        self.con.executemany(
            """
            INSERT INTO nodes
              (id, kind, name, qualname, module_path, lineno, end_lineno, docstring)
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
        self.con.commit()

    def _upsert_edges(self, edges: Iterable[Edge]) -> None:
        rows = [
            (
                e.src,
                e.rel,
                e.dst,
                json.dumps(e.evidence, ensure_ascii=False)
                if e.evidence is not None
                else None,
            )
            for e in edges
        ]
        self.con.executemany(
            """
            INSERT INTO edges (src, rel, dst, evidence)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(src, rel, dst) DO UPDATE SET
              evidence=excluded.evidence
            """,
            rows,
        )
        self.con.commit()

    # ------------------------------------------------------------------
    # Read — single node
    # ------------------------------------------------------------------

    def node(self, node_id: str) -> Optional[dict]:
        """
        Fetch a single node by id.

        :param node_id: Stable node identifier.
        :return: Node dict or ``None`` if not found.
        """
        row = self.con.execute(
            """
            SELECT id, kind, name, qualname, module_path, lineno, end_lineno, docstring
            FROM nodes WHERE id = ?
            """,
            (node_id,),
        ).fetchone()
        return _row_to_node(row) if row else None

    # ------------------------------------------------------------------
    # Read — filtered node lists
    # ------------------------------------------------------------------

    def query_nodes(
        self,
        *,
        kinds: Optional[Sequence[str]] = None,
        module: Optional[str] = None,
    ) -> List[dict]:
        """
        Return nodes matching optional filters.

        :param kinds: Restrict to these node kinds (e.g. ``["function", "method"]``).
        :param module: Restrict to nodes in this module path (exact match).
        :return: List of node dicts.
        """
        clauses: List[str] = []
        params: List[object] = []

        if kinds:
            placeholders = ",".join("?" for _ in kinds)
            clauses.append(f"kind IN ({placeholders})")
            params.extend(kinds)

        if module is not None:
            clauses.append("module_path = ?")
            params.append(module)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.con.execute(
            f"""
            SELECT id, kind, name, qualname, module_path, lineno, end_lineno, docstring
            FROM nodes {where}
            ORDER BY module_path, lineno
            """,
            params,
        ).fetchall()
        return [_row_to_node(r) for r in rows]

    # ------------------------------------------------------------------
    # Read — edges
    # ------------------------------------------------------------------

    def edges_within(self, node_ids: Set[str]) -> List[dict]:
        """
        Return all edges where both ``src`` and ``dst`` are in *node_ids*.

        :param node_ids: Set of node IDs to restrict to.
        :return: List of edge dicts with keys ``src``, ``rel``, ``dst``, ``evidence``.
        """
        if not node_ids:
            return []

        self.con.execute("DROP TABLE IF EXISTS _tmp_ids;")
        self.con.execute("CREATE TEMP TABLE _tmp_ids (id TEXT PRIMARY KEY);")
        self.con.executemany(
            "INSERT INTO _tmp_ids (id) VALUES (?)", [(i,) for i in node_ids]
        )
        rows = self.con.execute(
            """
            SELECT e.src, e.rel, e.dst, e.evidence
            FROM edges e
            JOIN _tmp_ids s ON s.id = e.src
            JOIN _tmp_ids d ON d.id = e.dst
            """
        ).fetchall()
        return [
            {"src": r[0], "rel": r[1], "dst": r[2], "evidence": r[3]} for r in rows
        ]

    # ------------------------------------------------------------------
    # Graph traversal
    # ------------------------------------------------------------------

    def expand(
        self,
        seed_ids: Set[str],
        *,
        hop: int = 1,
        rels: Tuple[str, ...] = DEFAULT_RELS,
    ) -> Dict[str, ProvMeta]:
        """
        Expand the graph from *seed_ids* up to *hop* hops.

        Returns a mapping from every reachable node ID to its
        :class:`ProvMeta` (minimum hop distance and originating seed).

        :param seed_ids: Starting node IDs (hop 0).
        :param hop: Maximum number of hops to traverse.
        :param rels: Edge relation types to follow.
        :return: ``{node_id: ProvMeta}`` for all reachable nodes.
        """
        rels = tuple(rels)
        meta: Dict[str, ProvMeta] = {
            sid: ProvMeta(best_hop=0, via_seed=sid) for sid in seed_ids
        }
        frontier: Set[str] = set(seed_ids)

        for h in range(1, hop + 1):
            nxt: Set[str] = set()
            for nid in frontier:
                rows = self.con.execute(
                    f"""
                    SELECT src, dst FROM edges
                    WHERE (src = ? OR dst = ?)
                      AND rel IN ({",".join("?" for _ in rels)})
                    """,
                    (nid, nid, *rels),
                ).fetchall()
                for src, dst in rows:
                    for cand in (src, dst):
                        if cand not in meta:
                            meta[cand] = ProvMeta(
                                best_hop=h,
                                via_seed=meta[nid].via_seed,
                            )
                            nxt.add(cand)
                        elif h < meta[cand].best_hop:
                            meta[cand] = ProvMeta(
                                best_hop=h,
                                via_seed=meta[nid].via_seed,
                            )
                            nxt.add(cand)
            frontier = nxt

        return meta

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        """
        Return node and edge counts by kind/relation.

        :return: dict with ``total_nodes``, ``total_edges``,
                 ``node_counts``, ``edge_counts``.
        """
        node_rows = self.con.execute(
            "SELECT kind, COUNT(*) FROM nodes GROUP BY kind"
        ).fetchall()
        edge_rows = self.con.execute(
            "SELECT rel, COUNT(*) FROM edges GROUP BY rel"
        ).fetchall()
        total_nodes = self.con.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        total_edges = self.con.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        return {
            "db_path": str(self.db_path),
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "node_counts": {r[0]: r[1] for r in node_rows},
            "edge_counts": {r[0]: r[1] for r in edge_rows},
        }

    def __repr__(self) -> str:
        return f"GraphStore(db_path={self.db_path!r})"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _row_to_node(row: tuple) -> dict:
    return {
        "id": row[0],
        "kind": row[1],
        "name": row[2],
        "qualname": row[3],
        "module_path": row[4],
        "lineno": row[5],
        "end_lineno": row[6],
        "docstring": row[7],
    }
