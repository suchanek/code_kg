#!/usr/bin/env python3
"""
build_codekg_sqlite.py

CLI entry point: repo → AST → SQLite

Uses the new CodeGraph + GraphStore classes.

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import argparse
from pathlib import Path

from code_kg.graph import CodeGraph
from code_kg.store import GraphStore


def main() -> None:
    p = argparse.ArgumentParser(
        description="Extract a code knowledge graph from a Python repo and store it in SQLite."
    )
    p.add_argument("--repo", default=".", help="Path to repository root (default: .)")
    p.add_argument(
        "--db",
        default=".codekg/graph.sqlite",
        help="SQLite database path (default: .codekg/graph.sqlite)",
    )
    p.add_argument("--wipe", action="store_true", help="Delete existing graph first")
    args = p.parse_args()

    repo_root = Path(args.repo).resolve()

    graph = CodeGraph(repo_root)
    nodes, edges = graph.extract().result()

    store = GraphStore(Path(args.db))
    store.write(nodes, edges, wipe=args.wipe)
    store.close()

    print(f"OK: nodes={len(nodes)} edges={len(edges)} db={args.db}")


if __name__ == "__main__":
    main()
