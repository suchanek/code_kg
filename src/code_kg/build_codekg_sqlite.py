#!/usr/bin/env python3
"""
build_codekg_sqlite.py

Repo -> AST -> nodes/edges -> SQLite

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import argparse
from pathlib import Path

from codekg_sqlite_v0 import connect_sqlite, write_graph

from codekg_v0 import extract_repo


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True, help="Path to repository root")
    p.add_argument("--db", required=True, help="SQLite db path")
    p.add_argument("--wipe", action="store_true", help="Delete existing graph first")
    args = p.parse_args()

    repo_root = Path(args.repo).resolve()
    nodes, edges = extract_repo(repo_root)

    con = connect_sqlite(Path(args.db))
    write_graph(con, nodes, edges, wipe=args.wipe)

    print(f"OK: nodes={len(nodes)} edges={len(edges)} db={args.db}")


if __name__ == "__main__":
    main()
