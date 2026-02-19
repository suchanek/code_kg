#!/usr/bin/env python3
"""
codekg_query.py

Hybrid query over Code Knowledge Graph:
- semantic retrieval (LanceDB vector search)
- structural expansion (SQLite)

Features:
- cache embed model
- filter symbol nodes by default
- print edges among returned nodes

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Dict, List, Set, Tuple

import lancedb

# -----------------------------------------------------------------------------
# SQLite helpers
# -----------------------------------------------------------------------------


def fetch_node(con: sqlite3.Connection, node_id: str) -> dict | None:
    row = con.execute(
        """
        SELECT id, kind, name, qualname, module_path, lineno, end_lineno, docstring
        FROM nodes WHERE id = ?
        """,
        (node_id,),
    ).fetchone()
    if not row:
        return None
    return dict(
        id=row[0],
        kind=row[1],
        name=row[2],
        qualname=row[3],
        module_path=row[4],
        lineno=row[5],
        end_lineno=row[6],
        docstring=row[7],
    )


def fetch_edges_between(con: sqlite3.Connection, node_ids: Set[str]) -> List[dict]:
    """
    Return edges where both src and dst are in node_ids.
    """
    if not node_ids:
        return []

    # Use a temp table for efficiency on large sets.
    con.execute("DROP TABLE IF EXISTS _tmp_ids;")
    con.execute("CREATE TEMP TABLE _tmp_ids (id TEXT PRIMARY KEY);")
    con.executemany("INSERT INTO _tmp_ids (id) VALUES (?)", [(i,) for i in node_ids])

    rows = con.execute(
        """
        SELECT e.src, e.rel, e.dst, e.evidence
        FROM edges e
        JOIN _tmp_ids s ON s.id = e.src
        JOIN _tmp_ids d ON d.id = e.dst
        """
    ).fetchall()

    return [dict(src=r[0], rel=r[1], dst=r[2], evidence=r[3]) for r in rows]


def expand_neighbors(
    con: sqlite3.Connection,
    node_ids: Set[str],
    *,
    hop: int = 1,
    rels: Tuple[str, ...] = ("CONTAINS", "CALLS", "IMPORTS", "INHERITS"),
) -> Set[str]:
    seen = set(node_ids)
    frontier = set(node_ids)

    for _ in range(hop):
        nxt = set()
        for nid in frontier:
            rows = con.execute(
                f"""
                SELECT src, dst FROM edges
                WHERE (src = ? OR dst = ?)
                  AND rel IN ({",".join("?" for _ in rels)})
                """,
                (nid, nid, *rels),
            ).fetchall()
            for src, dst in rows:
                if src not in seen:
                    nxt.add(src)
                if dst not in seen:
                    nxt.add(dst)
        seen |= nxt
        frontier = nxt

    return seen


# -----------------------------------------------------------------------------
# LanceDB helpers (VECTOR SEARCH, not FTS)
# -----------------------------------------------------------------------------

_MODEL = None


def semantic_search(
    lancedb_dir: Path,
    table: str,
    query: str,
    k: int,
    *,
    model_name: str,
) -> List[dict]:
    import numpy as np
    from sentence_transformers import SentenceTransformer

    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer(model_name)

    db = lancedb.connect(str(lancedb_dir))
    tbl = db.open_table(table)

    qvec = _MODEL.encode([query], normalize_embeddings=True)[0]
    qvec = np.asarray(qvec, dtype="float32").tolist()

    return tbl.search(qvec).limit(k).to_list()


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sqlite", required=True, help="Path to codekg.sqlite")
    p.add_argument("--lancedb", required=True, help="LanceDB directory")
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
        default="CONTAINS,CALLS,IMPORTS,INHERITS",
        help="Comma-separated edge types to expand",
    )
    p.add_argument(
        "--include-symbols", action="store_true", help="Include symbol nodes in output"
    )
    args = p.parse_args()

    rels = tuple(r.strip() for r in args.rels.split(",") if r.strip())

    hits = semantic_search(
        Path(args.lancedb), args.table, args.q, args.k, model_name=args.model
    )
    seed_ids = {h["id"] for h in hits}

    con = sqlite3.connect(str(Path(args.sqlite)))
    all_ids = expand_neighbors(con, seed_ids, hop=args.hop, rels=rels)

    # materialize nodes + filter
    nodes: List[dict] = []
    kept_ids: Set[str] = set()
    for nid in sorted(all_ids):
        n = fetch_node(con, nid)
        if not n:
            continue
        if (not args.include_symbols) and n["kind"] == "symbol":
            continue
        kept_ids.add(nid)
        nodes.append(n)

    edges = fetch_edges_between(con, kept_ids)
    con.close()

    print("=" * 80)
    print("QUERY:", args.q)
    print(
        f"Seeds: {len(seed_ids)} | Expanded(all): {len(all_ids)} | Returned(nodes): {len(nodes)} | hop={args.hop}"
    )
    print("Rels:", ",".join(rels), "| include_symbols:", args.include_symbols)
    print("=" * 80)

    for n in nodes:
        print(
            f"{n['kind']:8s} { (n['module_path'] or ''):40s} "
            f"{(n['qualname'] or n['name'])} [{n['id']}]"
        )
        if n["docstring"]:
            ds0 = n["docstring"].strip().splitlines()[0]
            print("    ", ds0[:120])
        print()

    print("-" * 80)
    print("EDGES (within returned node set):", len(edges))
    print("-" * 80)
    for e in sorted(edges, key=lambda x: (x["rel"], x["src"], x["dst"])):
        print(f"{e['src']} -[{e['rel']}]-> {e['dst']}")
    print("=" * 80)


if __name__ == "__main__":
    main()
