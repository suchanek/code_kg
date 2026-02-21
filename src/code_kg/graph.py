#!/usr/bin/env python3
"""
graph.py

CodeGraph — pure AST extraction class.

Wraps extract_repo() with a clean object interface.
No I/O, no persistence, no embeddings.

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

from pathlib import Path

from code_kg.codekg import Edge, Node, extract_repo


class CodeGraph:
    """
    Pure, deterministic AST extraction from a Python repository.

    Wraps the low-level ``extract_repo`` function with a cached,
    object-oriented interface.  No side effects; calling :meth:`extract`
    twice on the same root returns the same result.

    Example::

        graph = CodeGraph("/path/to/repo")
        graph.extract()
        print(f"{len(graph.nodes)} nodes, {len(graph.edges)} edges")

    :param repo_root: Path to the repository root directory.
    """

    def __init__(self, repo_root: str | Path) -> None:
        self.repo_root: Path = Path(repo_root).resolve()
        self._nodes: list[Node] | None = None
        self._edges: list[Edge] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, *, force: bool = False) -> CodeGraph:
        """
        Run AST extraction (cached after first call).

        :param force: Re-extract even if already cached.
        :return: self (for chaining)
        """
        if self._nodes is None or force:
            self._nodes, self._edges = extract_repo(self.repo_root)
        return self

    @property
    def nodes(self) -> list[Node]:
        """Extracted nodes (calls :meth:`extract` if needed)."""
        if self._nodes is None:
            self.extract()
        return self._nodes  # type: ignore[return-value]

    @property
    def edges(self) -> list[Edge]:
        """Extracted edges (calls :meth:`extract` if needed)."""
        if self._edges is None:
            self.extract()
        return self._edges  # type: ignore[return-value]

    def result(self) -> tuple[list[Node], list[Edge]]:
        """Return ``(nodes, edges)`` tuple."""
        return self.nodes, self.edges

    def stats(self) -> dict:
        """
        Return a summary of extracted nodes and edges by kind/relation.

        :return: dict with ``node_counts``, ``edge_counts``, ``total_nodes``,
                 ``total_edges``.
        """
        from collections import Counter

        node_counts: Counter = Counter(n.kind for n in self.nodes)
        edge_counts: Counter = Counter(e.rel for e in self.edges)
        return {
            "repo_root": str(self.repo_root),
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_counts": dict(node_counts),
            "edge_counts": dict(edge_counts),
        }

    def __repr__(self) -> str:
        extracted = self._nodes is not None
        if extracted:
            return (
                f"CodeGraph(repo_root={self.repo_root!r}, "
                f"nodes={len(self._nodes)}, edges={len(self._edges)})"  # type: ignore[arg-type]
            )
        return f"CodeGraph(repo_root={self.repo_root!r}, not yet extracted)"
