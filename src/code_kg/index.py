#!/usr/bin/env python3
"""
index.py

SemanticIndex — LanceDB vector index for the Code Knowledge Graph.

Derived from SQLite; disposable and rebuildable at any time.
SQLite (GraphStore) remains the authoritative source of truth.

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from code_kg.codekg import DEFAULT_MODEL

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

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of strings.

        :param texts: Input strings.
        :return: List of float32 vectors, one per input.
        """
        raise NotImplementedError

    def embed_query(self, query: str) -> list[float]:
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
                       Defaults to :data:`~code_kg.codekg.DEFAULT_MODEL`.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        """Load the sentence-transformer model.

        :param model_name: HuggingFace model name or local path.
        """
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        self.dim: int = self.model.get_sentence_embedding_dimension() or 384

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of strings into float32 vectors.

        :param texts: Input strings to embed.
        :return: List of float32 vectors, one per input string.
        """
        vecs = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [np.asarray(v, dtype="float32").tolist() for v in vecs]

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string into a float32 vector.

        :param query: Query string to embed.
        :return: Float32 vector representation of the query.
        """
        vec = self.model.encode([query], normalize_embeddings=True)[0]
        return np.asarray(vec, dtype="float32").tolist()

    def __repr__(self) -> str:
        """Return a developer-readable representation of this embedder.

        :return: String of the form ``SentenceTransformerEmbedder(model=..., dim=...)``.
        """
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
                     :data:`~code_kg.codekg.DEFAULT_MODEL`.
    :param table: LanceDB table name.  Defaults to ``"codekg_nodes"``.
    :param index_kinds: Node kinds to embed.
    """

    def __init__(
        self,
        lancedb_dir: str | Path,
        *,
        embedder: Embedder | None = None,
        table: str = _DEFAULT_TABLE,
        index_kinds: Sequence[str] = _DEFAULT_KINDS,
    ) -> None:
        """Initialise the semantic index.

        :param lancedb_dir: Directory for the LanceDB database.
        :param embedder: Embedding backend. Defaults to :class:`SentenceTransformerEmbedder`.
        :param table: LanceDB table name. Defaults to ``"codekg_nodes"``.
        :param index_kinds: Node kinds to include in the index.
        """
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
        store: GraphStore,  # type: ignore[name-defined]  # forward ref  # noqa: F821
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
                pred = " OR ".join([f"id = '{_escape(nid)}'" for nid in ids])
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

    def search(self, query: str, k: int = 8) -> list[SeedHit]:
        """
        Semantic vector search.

        :param query: Natural-language query string.
        :param k: Number of results to return.
        :return: List of :class:`SeedHit` ordered by ascending distance.
        """
        tbl = self._get_table()
        qvec = self.embedder.embed_query(query)
        raw = tbl.search(qvec).limit(k).to_list()

        hits: list[SeedHit] = []
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

    def _read_nodes(self, store: GraphStore) -> list[dict]:  # type: ignore[name-defined]  # noqa: F821
        """Read indexable nodes from the store filtered by ``index_kinds``.

        :param store: Authoritative :class:`~code_kg.store.GraphStore` to query.
        :return: List of node dicts for kinds in :attr:`index_kinds`.
        """
        return store.query_nodes(kinds=list(self.index_kinds))

    def _open_table(self, *, wipe: bool = False):
        """Open the LanceDB table, creating it with the correct schema if absent.

        :param wipe: If ``True``, delete all existing rows after opening.
        :return: LanceDB table handle.
        """
        import lancedb

        self.lancedb_dir.mkdir(parents=True, exist_ok=True)
        db = lancedb.connect(str(self.lancedb_dir))  # type: ignore[attr-defined]

        if self.table_name in db.list_tables().tables:
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
        """Return the cached LanceDB table handle, opening it if not yet loaded.

        :return: LanceDB table handle.
        """
        if self._tbl is None:
            import lancedb

            db = lancedb.connect(str(self.lancedb_dir))  # type: ignore[attr-defined]
            self._tbl = db.open_table(self.table_name)
        return self._tbl

    def __repr__(self) -> str:
        """Return a developer-readable representation of this SemanticIndex.

        :return: String including lancedb_dir, table name, and embedder details.
        """
        return (
            f"SemanticIndex(lancedb_dir={self.lancedb_dir!r}, "
            f"table={self.table_name!r}, embedder={self.embedder!r})"
        )


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


def _build_index_text(n: dict) -> str:
    """Build the canonical text document used for embedding a node.

    Stable — changing this format invalidates the existing index.

    :param n: Node dict with keys ``kind``, ``name``, ``qualname``, ``module_path``,
              ``lineno``, and optionally ``docstring``.
    :return: Newline-joined string suitable for embedding.
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
    """Extract a distance value from a LanceDB result row.

    Tries ``_distance``, then ``distance``, then inverts ``score``.
    Falls back to the row's rank if no distance field is found.

    :param row: Raw result dict from LanceDB.
    :param fallback_rank: Zero-based rank to use when no distance field is present.
    :return: Float distance value (lower = more similar).
    """
    for key in ("_distance", "distance"):
        if key in row and row[key] is not None:
            return float(row[key])
    if "score" in row and row["score"] is not None:
        return 1.0 / (1.0 + float(row["score"]))
    return float(fallback_rank)


def _escape(s: str) -> str:
    """Escape single quotes in a string for use in LanceDB delete predicates.

    :param s: String to escape.
    :return: String with single quotes doubled.
    """
    return s.replace("'", "''")
