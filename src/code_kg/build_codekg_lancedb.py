#!/usr/bin/env python3
"""
build_codekg_lancedb.py

CLI entry point: SQLite → LanceDB semantic index

Uses the new GraphStore + SemanticIndex classes.

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import argparse
from pathlib import Path

from code_kg.index import SemanticIndex, SentenceTransformerEmbedder
from code_kg.store import GraphStore


def main() -> None:
    p = argparse.ArgumentParser(
        description="Build a LanceDB semantic index from an existing codekg SQLite database."
    )
    p.add_argument("--sqlite", required=True, help="Path to codekg.sqlite")
    p.add_argument("--lancedb", required=True, help="Directory for LanceDB")
    p.add_argument("--table", default="codekg_nodes", help="LanceDB table name")
    p.add_argument(
        "--model", default="all-MiniLM-L6-v2", help="SentenceTransformer model name"
    )
    p.add_argument("--wipe", action="store_true", help="Delete existing vectors first")
    p.add_argument(
        "--kinds",
        default="module,class,function,method",
        help="Comma-separated node kinds to index",
    )
    p.add_argument("--batch", type=int, default=256, help="Embedding batch size")
    args = p.parse_args()

    kinds = tuple(k.strip() for k in args.kinds.split(",") if k.strip())
    embedder = SentenceTransformerEmbedder(args.model)

    store = GraphStore(Path(args.sqlite))
    idx = SemanticIndex(
        Path(args.lancedb),
        embedder=embedder,
        table=args.table,
        index_kinds=kinds,
    )
    stats = idx.build(store, wipe=args.wipe, batch_size=args.batch)
    store.close()

    print(
        "OK:",
        f"indexed_rows={stats['indexed_rows']}",
        f"dim={stats['dim']}",
        f"table={stats['table']}",
        f"lancedb_dir={stats['lancedb_dir']}",
        f"kinds={','.join(stats['kinds'])}",
    )


if __name__ == "__main__":
    main()
