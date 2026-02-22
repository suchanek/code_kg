#!/usr/bin/env python3
"""
kg.py

CodeKG — top-level orchestrator for the Code Knowledge Graph.

Owns the full pipeline:
    repo → CodeGraph → GraphStore → SemanticIndex → QueryResult / SnippetPack

Also defines the structured result types:
    BuildStats, QueryResult, SnippetPack

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from code_kg.graph import CodeGraph
from code_kg.index import Embedder, SemanticIndex, SentenceTransformerEmbedder
from code_kg.store import DEFAULT_RELS, GraphStore, ProvMeta

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_KIND_PRIORITY = {"function": 0, "method": 1, "class": 2, "module": 3, "symbol": 4}

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class BuildStats:
    """
    Statistics returned by :meth:`CodeKG.build` and related methods.

    :param repo_root: Repository root that was analysed.
    :param db_path: Path to the SQLite database.
    :param total_nodes: Total nodes written to SQLite.
    :param total_edges: Total edges written to SQLite.
    :param node_counts: Node counts broken down by kind.
    :param edge_counts: Edge counts broken down by relation.
    :param indexed_rows: Number of nodes embedded into LanceDB
                         (``None`` if the index was not built).
    :param index_dim: Embedding dimension (``None`` if not built).
    """

    repo_root: str
    db_path: str
    total_nodes: int
    total_edges: int
    node_counts: dict[str, int]
    edge_counts: dict[str, int]
    indexed_rows: int | None = None
    index_dim: int | None = None

    def to_dict(self) -> dict:
        return {
            "repo_root": self.repo_root,
            "db_path": self.db_path,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "node_counts": self.node_counts,
            "edge_counts": self.edge_counts,
            "indexed_rows": self.indexed_rows,
            "index_dim": self.index_dim,
        }

    def __str__(self) -> str:
        lines = [
            f"repo_root   : {self.repo_root}",
            f"db_path     : {self.db_path}",
            f"nodes       : {self.total_nodes}  {self.node_counts}",
            f"edges       : {self.total_edges}  {self.edge_counts}",
        ]
        if self.indexed_rows is not None:
            lines.append(f"indexed     : {self.indexed_rows} vectors  dim={self.index_dim}")
        return "\n".join(lines)


@dataclass
class QueryResult:
    """
    Result of a hybrid query (:meth:`CodeKG.query`).

    :param query: Original query string.
    :param seeds: Number of semantic seed nodes.
    :param expanded_nodes: Total nodes after graph expansion.
    :param returned_nodes: Nodes returned after filtering.
    :param hop: Hop count used.
    :param rels: Edge relations used for expansion.
    :param nodes: List of node dicts (sorted by rank).
    :param edges: List of edge dicts within the returned node set.
    """

    query: str
    seeds: int
    expanded_nodes: int
    returned_nodes: int
    hop: int
    rels: list[str]
    nodes: list[dict]
    edges: list[dict]

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "seeds": self.seeds,
            "expanded_nodes": self.expanded_nodes,
            "returned_nodes": self.returned_nodes,
            "hop": self.hop,
            "rels": self.rels,
            "nodes": self.nodes,
            "edges": self.edges,
        }

    def to_json(self, *, indent: int = 2) -> str:
        """Serialise to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def print_summary(self) -> None:
        """Print a human-readable summary to stdout."""
        sep = "=" * 80
        print(sep)
        print(f"QUERY: {self.query}")
        print(
            f"Seeds: {self.seeds} | Expanded: {self.expanded_nodes} "
            f"| Returned: {self.returned_nodes} | hop={self.hop}"
        )
        print(f"Rels: {', '.join(self.rels)}")
        print(sep)
        for n in self.nodes:
            print(
                f"{n['kind']:8s} {(n['module_path'] or ''):40s} "
                f"{n['qualname'] or n['name']}  [{n['id']}]"
            )
            if n.get("docstring"):
                ds0 = n["docstring"].strip().splitlines()[0]
                print(f"    {ds0[:120]}")
            print()
        print("-" * 80)
        print(f"EDGES (within returned set): {len(self.edges)}")
        print("-" * 80)
        for e in sorted(self.edges, key=lambda x: (x["rel"], x["src"], x["dst"])):
            print(f"  {e['src']} -[{e['rel']}]-> {e['dst']}")
        print(sep)


@dataclass
class Snippet:
    """
    A source-grounded code snippet.

    :param path: Repo-relative file path.
    :param start: 1-based start line (inclusive).
    :param end: 1-based end line (inclusive).
    :param text: Line-numbered source text.
    """

    path: str
    start: int
    end: int
    text: str

    def to_dict(self) -> dict:
        return {"path": self.path, "start": self.start, "end": self.end, "text": self.text}


@dataclass
class SnippetPack:
    """
    Result of :meth:`CodeKG.pack` — nodes with attached source snippets.

    :param query: Original query string.
    :param seeds: Number of semantic seed nodes.
    :param expanded_nodes: Total nodes after graph expansion.
    :param returned_nodes: Nodes returned after deduplication.
    :param hop: Hop count used.
    :param rels: Edge relations used for expansion.
    :param model: Embedding model name.
    :param nodes: Node dicts, each optionally containing a ``snippet`` key.
    :param edges: Edge dicts within the returned node set.
    """

    query: str
    seeds: int
    expanded_nodes: int
    returned_nodes: int
    hop: int
    rels: list[str]
    model: str
    nodes: list[dict]
    edges: list[dict]

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "seeds": self.seeds,
            "expanded_nodes": self.expanded_nodes,
            "returned_nodes": self.returned_nodes,
            "hop": self.hop,
            "rels": self.rels,
            "model": self.model,
            "nodes": self.nodes,
            "edges": self.edges,
        }

    def to_json(self, *, indent: int = 2) -> str:
        """Serialise to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_markdown(self) -> str:
        """Render as a Markdown context pack."""
        out: list[str] = []
        out.append("# CodeKG Snippet Pack\n")
        out.append(f"**Query:** `{self.query}`  ")
        out.append(f"**Seeds:** {self.seeds}  ")
        out.append(f"**Expanded nodes:** {self.expanded_nodes} (returned: {self.returned_nodes})  ")
        out.append(f"**hop:** {self.hop}  ")
        out.append(f"**rels:** {', '.join(self.rels)}  ")
        out.append(f"**model:** {self.model}  ")
        out.append("\n---\n")
        out.append("## Nodes\n")

        for n in self.nodes:
            out.append(f"### {n['kind']} — `{n.get('qualname') or n['name']}`")
            out.append(f"- id: `{n['id']}`")
            if n.get("module_path"):
                out.append(f"- module: `{n['module_path']}`")
            if n.get("lineno") is not None:
                out.append(f"- line: {n['lineno']}")
            if n.get("docstring"):
                ds0 = n["docstring"].strip().splitlines()[0]
                out.append(f"- doc: {ds0[:140]}")
            sn = n.get("snippet")
            if sn:
                out.append("")
                out.append(f"```python\n{sn['text']}\n```")
            out.append("")

        out.append("\n---\n")
        out.append("## Edges\n")
        for e in self.edges:
            out.append(f"- `{e['src']}` -[{e['rel']}]-> `{e['dst']}`")
        out.append("")
        return "\n".join(out)

    def save(self, path: str | Path, *, fmt: str = "md") -> None:
        """
        Write the pack to a file.

        :param path: Output file path.
        :param fmt: ``"md"`` for Markdown or ``"json"`` for JSON.
        """
        text = self.to_markdown() if fmt == "md" else self.to_json()
        Path(path).write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# CodeKG — orchestrator
# ---------------------------------------------------------------------------


class CodeKG:
    """
    Top-level orchestrator for the Code Knowledge Graph.

    Owns and coordinates all four layers:

    * :class:`~code_kg.graph.CodeGraph` — pure AST extraction
    * :class:`~code_kg.store.GraphStore` — SQLite persistence
    * :class:`~code_kg.index.SemanticIndex` — LanceDB vector index
    * Query / snippet-packing logic

    Typical usage::

        kg = CodeKG(
            repo_root="/path/to/repo",
            db_path=".codekg/graph.sqlite",
            lancedb_dir=".codekg/lancedb",
        )
        stats = kg.build(wipe=True)
        print(stats)

        result = kg.query("database connection setup", k=8, hop=1)
        result.print_summary()

        pack = kg.pack("configuration loading", k=8, hop=1)
        pack.save("context.md")

    :param repo_root: Repository root directory.
    :param db_path: SQLite database path.
    :param lancedb_dir: LanceDB directory.
    :param model: Sentence-transformer model name.
    :param table: LanceDB table name.
    """

    def __init__(
        self,
        repo_root: str | Path,
        db_path: str | Path,
        lancedb_dir: str | Path,
        *,
        model: str = "all-MiniLM-L6-v2",
        table: str = "codekg_nodes",
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.db_path = Path(db_path)
        self.lancedb_dir = Path(lancedb_dir)
        self.model_name = model
        self.table_name = table

        # Lazy-initialised layers
        self._graph: CodeGraph | None = None
        self._store: GraphStore | None = None
        self._index: SemanticIndex | None = None
        self._embedder: Embedder | None = None

    # ------------------------------------------------------------------
    # Layer accessors (lazy init)
    # ------------------------------------------------------------------

    @property
    def graph(self) -> CodeGraph:
        """AST extraction layer (lazy)."""
        if self._graph is None:
            self._graph = CodeGraph(self.repo_root)
        return self._graph

    @property
    def store(self) -> GraphStore:
        """SQLite persistence layer (lazy)."""
        if self._store is None:
            self._store = GraphStore(self.db_path)
        return self._store

    @property
    def embedder(self) -> Embedder:
        """Embedding backend (lazy, shared between index and query)."""
        if self._embedder is None:
            self._embedder = SentenceTransformerEmbedder(self.model_name)
        return self._embedder

    @property
    def index(self) -> SemanticIndex:
        """LanceDB semantic index (lazy)."""
        if self._index is None:
            self._index = SemanticIndex(
                self.lancedb_dir,
                embedder=self.embedder,
                table=self.table_name,
            )
        return self._index

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self, *, wipe: bool = False) -> BuildStats:
        """
        Full pipeline: AST extraction → SQLite → LanceDB.

        :param wipe: Clear existing data before writing.
        :return: :class:`BuildStats`.
        """
        graph_stats = self.build_graph(wipe=wipe)
        index_stats = self.build_index(wipe=wipe)
        graph_stats.indexed_rows = index_stats.indexed_rows
        graph_stats.index_dim = index_stats.index_dim
        return graph_stats

    def build_graph(self, *, wipe: bool = False) -> BuildStats:
        """
        AST extraction → SQLite only.

        :param wipe: Clear existing graph before writing.
        :return: :class:`BuildStats` (``indexed_rows`` will be ``None``).
        """
        nodes, edges = self.graph.extract(force=wipe).result()
        self.store.write(nodes, edges, wipe=wipe)
        s = self.store.stats()
        return BuildStats(
            repo_root=str(self.repo_root),
            db_path=str(self.db_path),
            total_nodes=s["total_nodes"],
            total_edges=s["total_edges"],
            node_counts=s["node_counts"],
            edge_counts=s["edge_counts"],
        )

    def build_index(self, *, wipe: bool = False) -> BuildStats:
        """
        SQLite → LanceDB only (graph must already exist).

        :param wipe: Delete existing vectors before indexing.
        :return: :class:`BuildStats` with ``indexed_rows`` and ``index_dim`` set.
        """
        idx_stats = self.index.build(self.store, wipe=wipe)
        s = self.store.stats()
        return BuildStats(
            repo_root=str(self.repo_root),
            db_path=str(self.db_path),
            total_nodes=s["total_nodes"],
            total_edges=s["total_edges"],
            node_counts=s["node_counts"],
            edge_counts=s["edge_counts"],
            indexed_rows=idx_stats["indexed_rows"],
            index_dim=idx_stats["dim"],
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        q: str,
        *,
        k: int = 8,
        hop: int = 1,
        rels: tuple[str, ...] = DEFAULT_RELS,
        include_symbols: bool = False,
        max_nodes: int = 25,
    ) -> QueryResult:
        """
        Hybrid query: semantic seeding + structural expansion.

        :param q: Natural-language query.
        :param k: Top-K semantic hits.
        :param hop: Graph expansion hops.
        :param rels: Edge types to expand.
        :param include_symbols: Include ``symbol`` nodes in results.
        :param max_nodes: Maximum nodes to return (default 25).
        :return: :class:`QueryResult`.
        """
        hits = self.index.search(q, k=k)
        seed_ids: set[str] = {h.id for h in hits}

        meta = self.store.expand(seed_ids, hop=hop, rels=rels)
        all_ids = set(meta.keys())

        nodes: list[dict] = []
        kept_ids: set[str] = set()
        for nid in sorted(all_ids):
            if len(nodes) >= max_nodes:
                break
            n = self.store.node(nid)
            if not n:
                continue
            if not include_symbols and n["kind"] == "symbol":
                continue
            kept_ids.add(nid)
            nodes.append(n)

        edges = self.store.edges_within(kept_ids)

        return QueryResult(
            query=q,
            seeds=len(seed_ids),
            expanded_nodes=len(all_ids),
            returned_nodes=len(nodes),
            hop=hop,
            rels=list(rels),
            nodes=nodes,
            edges=edges,
        )

    # ------------------------------------------------------------------
    # Snippet pack
    # ------------------------------------------------------------------

    def pack(
        self,
        q: str,
        *,
        k: int = 8,
        hop: int = 1,
        rels: tuple[str, ...] = DEFAULT_RELS,
        include_symbols: bool = False,
        context: int = 5,
        max_lines: int = 60,
        max_nodes: int = 15,
    ) -> SnippetPack:
        """
        Hybrid query + source-grounded snippet extraction.

        :param q: Natural-language query.
        :param k: Top-K semantic hits.
        :param hop: Graph expansion hops.
        :param rels: Edge types to expand.
        :param include_symbols: Include ``symbol`` nodes.
        :param context: Extra context lines around each definition span.
        :param max_lines: Maximum lines per snippet block (default 60).
        :param max_nodes: Maximum nodes to return (default 15).
        :return: :class:`SnippetPack`.
        """
        hits = self.index.search(q, k=k)
        seed_rank: dict[str, dict] = {h.id: {"rank": h.rank, "dist": h.distance} for h in hits}
        seed_ids: set[str] = set(seed_rank.keys())

        meta = self.store.expand(seed_ids, hop=hop, rels=rels)
        all_ids = set(meta.keys())

        # Materialise + annotate nodes
        raw_nodes: list[dict] = []
        for nid in sorted(all_ids):
            n = self.store.node(nid)
            if not n:
                continue
            if not include_symbols and n["kind"] == "symbol":
                continue

            prov: ProvMeta = meta[nid]
            base_dist = seed_rank.get(prov.via_seed, {"dist": 1e9})["dist"]
            kind_pri = _KIND_PRIORITY.get(n["kind"], 99)
            n["_rank_key"] = (prov.best_hop, base_dist, kind_pri, n["id"])
            n["_best_hop"] = prov.best_hop
            n["_via_seed"] = prov.via_seed
            raw_nodes.append(n)

        # Attach spans (needed for dedup)
        file_cache: dict[str, list[str]] = {}
        for n in raw_nodes:
            mp = n.get("module_path")
            if not mp:
                n["_span"] = None
                continue
            if mp not in file_cache:
                file_cache[mp] = _read_lines(_safe_join(self.repo_root, mp))
            lines = file_cache[mp]
            n["_span"] = _compute_span(
                n["kind"],
                n.get("lineno"),
                n.get("end_lineno"),
                context=context,
                max_lines=max_lines,
                file_nlines=len(lines),
            )

        # Rank
        raw_nodes.sort(key=lambda x: x["_rank_key"])

        # Deduplicate by file + overlapping span
        kept: list[dict] = []
        kept_by_file: dict[str, list[tuple[tuple[int, int], str]]] = {}

        for n in raw_nodes:
            if len(kept) >= max_nodes:
                break
            mp = n.get("module_path") or ""
            span = n.get("_span")

            if not mp or not span or span[1] < span[0]:
                kept.append(n)
                continue

            if any(_spans_overlap(span, s2) for s2, _ in kept_by_file.get(mp, [])):
                continue

            kept.append(n)
            kept_by_file.setdefault(mp, []).append((span, n["id"]))

        kept_ids: set[str] = {n["id"] for n in kept}
        edges = self.store.edges_within(kept_ids)

        # Attach snippets
        for n in kept:
            mp = n.get("module_path")
            span = n.get("_span")
            if not mp or not span:
                continue
            if mp not in file_cache:
                file_cache[mp] = _read_lines(_safe_join(self.repo_root, mp))
            lines = file_cache[mp]
            start, end = span
            if end >= start and lines:
                n["snippet"] = _make_snippet(mp, lines, start, end)

        # Strip internal keys
        for n in kept:
            for key in [k for k in n if k.startswith("_")]:
                del n[key]

        return SnippetPack(
            query=q,
            seeds=len(seed_ids),
            expanded_nodes=len(all_ids),
            returned_nodes=len(kept),
            hop=hop,
            rels=list(rels),
            model=self.model_name,
            nodes=kept,
            edges=edges,
        )

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        """Return store statistics (node/edge counts by kind/relation)."""
        return self.store.stats()

    def node(self, node_id: str) -> dict | None:
        """Fetch a single node by ID from the store."""
        return self.store.node(node_id)

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        if self._store is not None:
            self._store.close()

    def __enter__(self) -> CodeKG:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"CodeKG(repo_root={self.repo_root!r}, "
            f"db_path={self.db_path!r}, "
            f"lancedb_dir={self.lancedb_dir!r}, "
            f"model={self.model_name!r})"
        )


# ---------------------------------------------------------------------------
# Snippet utilities (private to this module)
# ---------------------------------------------------------------------------


def _safe_join(repo_root: Path, rel_path: str) -> Path:
    p = (repo_root / rel_path).resolve()
    rr = repo_root.resolve()
    if rr not in p.parents and p != rr:
        raise ValueError(f"Unsafe path outside repo_root: {rel_path!r}")
    return p


def _read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except FileNotFoundError:
        return []


def _compute_span(
    kind: str,
    lineno: int | None,
    end_lineno: int | None,
    *,
    context: int,
    max_lines: int,
    file_nlines: int,
) -> tuple[int, int]:
    if file_nlines <= 0:
        return (1, 0)
    if kind == "module":
        return (1, min(file_nlines, max_lines))
    if lineno is None:
        return (1, min(file_nlines, max_lines))
    if end_lineno is not None and end_lineno >= lineno:
        start = max(1, lineno - context)
        end = min(file_nlines, end_lineno + context)
        if (end - start + 1) > max_lines:
            end = min(file_nlines, start + max_lines - 1)
        return (start, end)
    start = max(1, lineno - context)
    end = min(file_nlines, lineno + context)
    if (end - start + 1) > max_lines:
        end = min(file_nlines, start + max_lines - 1)
    return (start, end)


def _make_snippet(rel_path: str, lines: list[str], start: int, end: int) -> dict:
    s0 = max(0, start - 1)
    e0 = max(0, end)
    chunk = lines[s0:e0]
    numbered = "\n".join(f"{i:>5d}: {line}" for i, line in enumerate(chunk, start=start))
    return {"path": rel_path, "start": start, "end": end, "text": numbered}


def _spans_overlap(a: tuple[int, int], b: tuple[int, int], gap: int = 2) -> bool:
    a0, a1 = a
    b0, b1 = b
    return not (a1 + gap < b0 or b1 + gap < a0)
