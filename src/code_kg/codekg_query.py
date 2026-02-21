#!/usr/bin/env python3
"""
codekg_query.py

CLI entry point: hybrid query over the Code Knowledge Graph.

Uses the new CodeKG orchestrator.

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import argparse
from pathlib import Path

from code_kg.kg import CodeKG
from code_kg.store import DEFAULT_RELS


def main() -> None:
    p = argparse.ArgumentParser(
        description="Hybrid query (semantic + graph) over a codekg database."
    )
    p.add_argument(
        "--sqlite",
        default=".codekg/graph.sqlite",
        help="Path to graph.sqlite (default: .codekg/graph.sqlite)",
    )
    p.add_argument(
        "--lancedb",
        default=".codekg/lancedb",
        help="LanceDB directory (default: .codekg/lancedb)",
    )
    p.add_argument("--table", default="codekg_nodes", help="LanceDB table name")
    p.add_argument(
        "--model",
        default="all-MiniLM-L6-v2",
        help="SentenceTransformer model (must match index)",
    )
    p.add_argument("--q", required=True, help="Semantic query")
    p.add_argument("--k", type=int, default=8, help="Top-k semantic hits")
    p.add_argument("--hop", type=int, default=1, help="Graph expansion hops")
    p.add_argument(
        "--rels",
        default=",".join(DEFAULT_RELS),
        help="Comma-separated edge types to expand",
    )
    p.add_argument("--include-symbols", action="store_true", help="Include symbol nodes in output")
    # repo_root is not needed for query-only; use db_path as a stand-in
    args = p.parse_args()

    rels = tuple(r.strip() for r in args.rels.split(",") if r.strip())

    # CodeKG needs a repo_root for snippet packing, but query-only doesn't use it.
    # We pass the sqlite parent dir as a safe placeholder.
    repo_root = Path(args.sqlite).parent

    kg = CodeKG(
        repo_root=repo_root,
        db_path=Path(args.sqlite),
        lancedb_dir=Path(args.lancedb),
        model=args.model,
        table=args.table,
    )

    result = kg.query(
        args.q,
        k=args.k,
        hop=args.hop,
        rels=rels,
        include_symbols=args.include_symbols,
    )
    result.print_summary()
    kg.close()


if __name__ == "__main__":
    main()
