#!/usr/bin/env python3
"""
codekg_snippet_packer.py

CLI entry point: hybrid retrieval + source-grounded snippet packing.

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
        description="Hybrid query + snippet packing over a codekg database."
    )
    p.add_argument(
        "--repo-root",
        default=".",
        help="Root of the source tree used to build the KG (default: .)",
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
        help="Embedding model name (must match index)",
    )
    p.add_argument("--q", required=True, help="Semantic query")
    p.add_argument("--k", type=int, default=8, help="Top-k semantic hits")
    p.add_argument("--hop", type=int, default=1, help="Graph expansion hops")
    p.add_argument(
        "--rels",
        default=",".join(DEFAULT_RELS),
        help="Comma-separated rels to expand",
    )
    p.add_argument(
        "--include-symbols",
        action="store_true",
        help="Include symbol nodes (default: false)",
    )
    p.add_argument(
        "--context",
        type=int,
        default=5,
        help="Extra context lines before/after definition span",
    )
    p.add_argument("--max-lines", type=int, default=160, help="Max lines per snippet block")
    p.add_argument(
        "--max-nodes",
        type=int,
        default=50,
        help="Max nodes returned in pack (deterministic truncation)",
    )
    p.add_argument("--format", choices=["json", "md"], default="md", help="Output format")
    p.add_argument("--out", default="", help="Output path (default: stdout)")
    args = p.parse_args()

    rels = tuple(r.strip() for r in args.rels.split(",") if r.strip())

    kg = CodeKG(
        repo_root=Path(args.repo_root),
        db_path=Path(args.sqlite),
        lancedb_dir=Path(args.lancedb),
        model=args.model,
        table=args.table,
    )

    pack = kg.pack(
        args.q,
        k=args.k,
        hop=args.hop,
        rels=rels,
        include_symbols=args.include_symbols,
        context=args.context,
        max_lines=args.max_lines,
        max_nodes=args.max_nodes,
    )
    kg.close()

    if args.format == "json":
        text = pack.to_json()
    else:
        text = pack.to_markdown()

    if args.out:
        pack.save(args.out, fmt=args.format)
        print(f"OK: wrote {args.format} to {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
