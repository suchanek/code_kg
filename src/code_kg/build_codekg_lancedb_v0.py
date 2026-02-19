#!/usr/bin/env python3
"""
build_codekg_lancedb.py

Build LanceDB semantic index from an existing codekg SQLite database.

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import argparse
from pathlib import Path

from codekg_lancedb_v0 import SentenceTransformerEmbedder, rebuild_lancedb_index


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sqlite", required=True, help="Path to codekg.sqlite")
    p.add_argument("--lancedb", required=True, help="Directory for LanceDB")
    p.add_argument("--table", default="codekg_nodes", help="LanceDB table name")
    p.add_argument(
        "--model", default="all-MiniLM-L6-v2", help="SentenceTransformer model"
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
    emb = SentenceTransformerEmbedder(args.model)

    stats = rebuild_lancedb_index(
        sqlite_path=Path(args.sqlite),
        lancedb_dir=Path(args.lancedb),
        table_name=args.table,
        embedder=emb,
        include_kinds=kinds,
        wipe=args.wipe,
        batch_size=args.batch,
    )

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
