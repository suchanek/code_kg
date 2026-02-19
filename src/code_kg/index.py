#!/usr/bin/env python3
"""
index.py

SemanticIndex — LanceDB vector index for the Code Knowledge Graph.

Derived from SQLite; disposable and rebuildable at any time.
SQLite (GraphStore) remains the authoritative source of truth.

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

import numpy as np

# ---------------------------------------------------------------------------
# Embedder interface (pluggable)
# ---------------------------------------------------------------------------


class Embedder:
    """
    Abstract embedding backend.

    Subclass and implement :meth:`embed_texts` to plug in any model.

    :param dim: Embedding dimension (must be set by subclass ``__init__``).
    """

    dim: int

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of strings.

        :param texts: Input strings.
        :return: List of float32 vectors, one per input.
        """
        raise NotImplementedError

    def embed_query(self, query: str) -> List[float]:
        """
        Embed a single query string.

        Default implementation calls :meth:`embed_texts` with a one-element list.

        :param query: Query string.
        :return: Float32 vector.
        """
        return self.embed_texts([query])[0]


class SentenceTransformerEmbedder(Embedder):
    """
    Local embedding via ``sentence-transformers``.

    :param model_name: HuggingFace model name or local path.
                       Defaults to ``"all-MiniLM-L6-v2"``.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        self.dim: int = self.model.get_sentence_embedding_dimension()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        vecs = self.model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        return [np.asarray(v, dtype="float32").tolist() for v in vecs]

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query string."""
        vec = self.model.encode([query], normalize_embeddings=True)[0]
        return np.asarray(vec, dtype="float32").tolist()

    def __repr__(self) -> str:
        return f"SentenceTransformerEmbedder(model={self.model_name!r}, dim={self.dim})"


# ---------------------------------------------------------------------------
# Seed hit returned by SemanticIndex.search()
# ---------------------------------------------------------------------------


@dataclass
class SeedHit:
    """
    A single result from a semantic vector search.

    :param id: Node ID.
    :param kind: Node kind (``module``, ``class``, ``function``, ``method``).
    :param name: Short name.
    :param qualname: Qualified name.
    :param module_path: Repo-relative module path.
    :param distance: Vector distance (lower = more similar).
    :param rank: Zero-based rank in the result list.
    """

    id: str
    kind: str
    name: str
    qualname: str
    module_path: str
    distance: float
    rank: int


# ---------------------------------------------------------------------------
# SemanticIndex
# ---------------------------------------------------------------------------

_DEFAULT_TABLE = "codekg_nodes"
_DEFAULT_KINDS = ("module", "class", "function", "method")


class SemanticIndex:
    """
    LanceDB-backed semantic vector index for the Code Knowledge Graph.

    Reads nodes from a :class:`~code_kg.store.GraphStore` (via its SQLite
    database), embeds them, and stores the vectors in LanceDB.  The index
    is **derived and disposable** — it can be rebuilt from SQLite at any
    time without data loss.

    Example::

        embedder = SentenceTransformerEmbedder()
        idx = SemanticIndex("./lancedb", embedder=embedder)
        idx.build(store, wipe=True)

        hits = idx.search("database connection setup", k=8)
        for h in hits:
            print(h.id, h.distance)

    :param lancedb_dir: Directory for the LanceDB database.
    :param embedder: Embedding backend.  Defaults to
                     :class:`SentenceTransformerEmbedder` with
                     ``all-MiniLM-L6-v2``.
    :param table: LanceDB table name.  Defaults to ``"codekg_nodes"``.
    :param index_kinds: Node kinds to embed.
    """

    def __init__(
        self,
        lancedb_dir: str | Path,
        *,
        embedder: Optional[Embedder] = None,
        table: str = _DEFAULT_TABLE,
        index_kinds: Sequence[str] = _DEFAULT_KINDS,
    ) -> None:
        self.lancedb_dir = Path(lancedb_dir)
        self.embedder: Embedder = embedder or SentenceTransformerEmbedder()
        self.table_name = table
        self.index_kinds = tuple(index_kinds)
        self._tbl = None  # lazy LanceDB table handle

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(
        self,
        store: "GraphStore",  # type: ignore[name-defined]  # forward ref
        *,
        wipe: bool = False,
        batch_size: int = 256,
    ) -> dict:
        """
        Build (or rebuild) the vector index from *store*.

        :param store: Authoritative :class:`~code_kg.store.GraphStore`.
        :param wipe: If ``True``, delete all existing vectors first.
        :param batch_size: Number of nodes to embed per batch.
        :return: Stats dict with ``indexed_rows``, ``dim``, ``table``,
                 ``lancedb_dir``, ``kinds``.
        """
        nodes = self._read_nodes(store)
        tbl = self._open_table(wipe=wipe)

        if wipe:
            tbl.delete("id != ''")

        indexed = 0
        for i in range(0, len(nodes), batch_size):
            chunk = nodes[i : i + batch_size]
            texts = [_build_index_text(n) for n in chunk]
            vecs = self.embedder.embed_texts(texts)

            # upsert: delete existing IDs then add fresh rows
            ids = [n["id"] for n in chunk]
            if ids:
                pred = " OR ".join(
                    [f"id = '{_escape(nid)}'" for nid in ids]
                )
                tbl.delete(pred)

            rows = [
                {
                    "id": n["id"],
                    "kind": n["kind"],
                    "name": n["name"],
                    "qualname": n["qualname"] or "",
                    "module_path": n["module_path"] or "",
                    "text": text,
                    "vector": vec,
                }
                for n, text, vec in zip(chunk, texts, vecs)
            ]
            tbl.add(rows)
            indexed += len(rows)

        self._tbl = tbl
        return {
            "indexed_rows": indexed,
            "dim": self.embedder.dim,
            "table": self.table_name,
            "lancedb_dir": str(self.lancedb_dir),
            "kinds": list(self.index_kinds),
        }

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, k: int = 8) -> List[SeedHit]:
        """
        Semantic vector search.

        :param query: Natural-language query string.
        :param k: Number of results to return.
        :return: List of :class:`SeedHit` ordered by ascending distance.
        """
        tbl = self._get_table()
        qvec = self.embedder.embed_query(query)
        raw = tbl.search(qvec).limit(k).to_list()

        hits: List[SeedHit] = []
        for rank, row in enumerate(raw):
            dist = _extract_distance(row, rank)
            hits.append(
                SeedHit(
                    id=row["id"],
                    kind=row.get("kind", ""),
                    name=row.get("name", ""),
                    qualname=row.get("qualname", ""),
                    module_path=row.get("module_path", ""),
                    distance=dist,
                    rank=rank,
                )
            )
        return hits

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_nodes(self, store: "GraphStore") -> List[dict]:  # type: ignore[name-defined]
        """Read indexable nodes from the store."""
        return store.query_nodes(kinds=list(self.index_kinds))

    def _open_table(self, *, wipe: bool = False):
        """Open or create the LanceDB table."""
        import lancedb

        self.lancedb_dir.mkdir(parents=True, exist_ok=True)
        db = lancedb.connect(str(self.lancedb_dir))

        if self.table_name in db.table_names():
            tbl = db.open_table(self.table_name)
            if wipe:
                tbl.delete("id != ''")
            return tbl

        # Create with a dummy row to establish schema, then remove it
        dummy = {
            "id": "__dummy__",
            "kind": "dummy",
            "name": "__dummy__",
            "qualname": "",
            "module_path": "",
            "text": "__dummy__",
            "vector": np.zeros((self.embedder.dim,), dtype="float32").tolist(),
        }
        tbl = db.create_table(self.table_name, data=[dummy])
        tbl.delete("id = '__dummy__'")
        return tbl

    def _get_table(self):
        """Return cached table handle, opening if needed."""
        if self._tbl is None:
            import lancedb

            db = lancedb.connect(str(self.lancedb_dir))
            self._tbl = db.open_table(self.table_name)
        return self._tbl

    def __repr__(self) -> str:
        return (
            f"SemanticIndex(lancedb_dir={self.lancedb_dir!r}, "
            f"table={self.table_name!r}, embedder={self.embedder!r})"
        )


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


def _build_index_text(n: dict) -> str:
    """
    Canonical text document used for embedding.

    Stable — changing this invalidates the index.
    """
    parts = [f"KIND: {n['kind']}", f"NAME: {n['name']}"]
    if n.get("qualname"):
        parts.append(f"QUALNAME: {n['qualname']}")
    if n.get("module_path"):
        parts.append(f"MODULE: {n['module_path']}")
    if n.get("lineno") is not None:
        parts.append(f"LINE: {n['lineno']}")
    if n.get("docstring"):
        parts.append("DOCSTRING:\n" + n["docstring"].strip())
    return "\n".join(parts)


def _extract_distance(row: dict, fallback_rank: int) -> float:
    """Extract a distance value from a LanceDB result row."""
    for key in ("_distance", "distance"):
        if key in row and row[key] is not None:
            return float(row[key])
    if "score" in row and row["score"] is not None:
        return 1.0 / (1.0 + float(row["score"]))
    return float(fallback_rank)


def _escape(s: str) -> str:
    """Escape single quotes for LanceDB delete predicates."""
    return s.replace("'", "''")
