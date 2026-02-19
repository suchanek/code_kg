#!/usr/bin/env python3
"""
codekg_snippet_packer_v0.py

Hybrid retrieval + snippet packing for the Code Knowledge Graph (v0).

Pipeline:
  query -> LanceDB vector search -> seed node ids
        -> SQLite expansion -> nodes
        -> source snippets from repo_root -> context pack

SQLite is authoritative. LanceDB is acceleration.
Snippets are derived from on-disk source.

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

import lancedb

# -----------------------------------------------------------------------------
# LanceDB vector search (avoid FTS)
# -----------------------------------------------------------------------------

_MODEL = None


def lancedb_vector_search(
    lancedb_dir: Path,
    table: str,
    query: str,
    k: int,
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
# SQLite access
# -----------------------------------------------------------------------------


def fetch_node(con: sqlite3.Connection, node_id: str) -> Optional[dict]:
    row = con.execute(
        """
        SELECT id, kind, name, qualname, module_path, lineno, end_lineno, docstring
        FROM nodes WHERE id = ?
        """,
        (node_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "kind": row[1],
        "name": row[2],
        "qualname": row[3],
        "module_path": row[4],
        "lineno": row[5],
        "end_lineno": row[6],
        "docstring": row[7],
    }


def expand_neighbors(
    con: sqlite3.Connection,
    node_ids: Set[str],
    *,
    hop: int = 1,
    rels: Sequence[str] = ("CONTAINS", "CALLS", "IMPORTS", "INHERITS"),
) -> Set[str]:
    seen = set(node_ids)
    frontier = set(node_ids)

    rels = tuple(rels)
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


def edges_within_set(con: sqlite3.Connection, node_ids: Set[str]) -> List[dict]:
    if not node_ids:
        return []

    # Temp table for efficient join
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

    return [{"src": r[0], "rel": r[1], "dst": r[2], "evidence": r[3]} for r in rows]


# -----------------------------------------------------------------------------
# Snippet extraction
# -----------------------------------------------------------------------------


def safe_join(repo_root: Path, rel_path: str) -> Path:
    """
    Prevent path traversal: ensure repo_root/rel_path stays under repo_root.
    """
    p = (repo_root / rel_path).resolve()
    rr = repo_root.resolve()
    if rr not in p.parents and p != rr:
        raise ValueError(f"Unsafe path outside repo_root: {rel_path}")
    return p


def read_lines(path: Path) -> List[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        # fallback: ignore errors to still get something
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except FileNotFoundError:
        return []


def compute_span(
    kind: str,
    lineno: Optional[int],
    end_lineno: Optional[int],
    *,
    context: int,
    max_lines: int,
    file_nlines: int,
) -> Tuple[int, int]:
    """
    Return 1-based inclusive (start, end) span.
    """
    if file_nlines <= 0:
        return (1, 0)

    if kind == "module":
        # For modules, show top-of-file window
        start = 1
        end = min(file_nlines, max_lines)
        return (start, end)

    if lineno is None:
        # unknown location: top window
        return (1, min(file_nlines, max_lines))

    if end_lineno is not None and end_lineno >= lineno:
        # Use AST span but cap size
        start = max(1, lineno - context)
        end = min(file_nlines, end_lineno + context)
        if (end - start + 1) > max_lines:
            end = min(file_nlines, start + max_lines - 1)
        return (start, end)

    # fallback: symmetric window around lineno
    start = max(1, lineno - context)
    end = min(file_nlines, lineno + context)
    if (end - start + 1) > max_lines:
        end = min(file_nlines, start + max_lines - 1)
    return (start, end)


def make_snippet(rel_path: str, lines: List[str], start: int, end: int) -> dict:
    """
    Produce a snippet record with line numbers.
    """
    # convert to 0-based indices
    s0 = max(0, start - 1)
    e0 = max(0, end)  # slice end is exclusive; end is inclusive
    chunk = lines[s0:e0]

    # Add line numbers to text block
    numbered = "\n".join(
        f"{i:>5d}: {line}" for i, line in enumerate(chunk, start=start)
    )

    return {
        "path": rel_path,
        "start": start,
        "end": end,
        "text": numbered,
    }


def expand_with_provenance(
    con: sqlite3.Connection,
    seed_ids: Set[str],
    *,
    hop: int,
    rels: Sequence[str],
) -> Dict[str, dict]:
    """
    Expand neighbors up to `hop` with provenance:
    - best_hop: minimum hop distance from any seed
    - via_seed: which seed yielded the best path (for tie-breaking)
    """
    rels = tuple(rels)

    meta: Dict[str, dict] = {sid: {"best_hop": 0, "via_seed": sid} for sid in seed_ids}
    frontier: Set[str] = set(seed_ids)

    for h in range(1, hop + 1):
        nxt: Set[str] = set()
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
                for cand in (src, dst):
                    if cand not in meta:
                        meta[cand] = {"best_hop": h, "via_seed": meta[nid]["via_seed"]}
                        nxt.add(cand)
                    else:
                        # If we found a shorter path, update deterministically.
                        if h < meta[cand]["best_hop"]:
                            meta[cand] = {
                                "best_hop": h,
                                "via_seed": meta[nid]["via_seed"],
                            }
                            nxt.add(cand)
        frontier = nxt

    return meta


def spans_overlap(a: Tuple[int, int], b: Tuple[int, int], gap: int = 2) -> bool:
    """
    Inclusive span overlap with a small gap allowance.
    """
    a0, a1 = a
    b0, b1 = b
    return not (a1 + gap < b0 or b1 + gap < a0)


# -----------------------------------------------------------------------------
# Packing / output
# -----------------------------------------------------------------------------


def to_markdown(pack: dict) -> str:
    out = []
    out.append(f"# CodeKG Snippet Pack\n")
    out.append(f"**Query:** `{pack['query']}`  \n")
    out.append(f"**Seeds:** {pack['seeds']}  \n")
    out.append(
        f"**Expanded nodes:** {pack['expanded_nodes']} (returned: {pack['returned_nodes']})  \n"
    )
    out.append(f"**hop:** {pack['hop']}  \n")
    out.append(f"**rels:** {', '.join(pack['rels'])}  \n")

    out.append("\n---\n")
    out.append("## Nodes\n")
    for n in pack["nodes"]:
        out.append(f"### {n['kind']} — `{n['qualname'] or n['name']}`")
        out.append(f"- id: `{n['id']}`")
        if n.get("module_path"):
            out.append(f"- module: `{n['module_path']}`")
        if n.get("lineno") is not None:
            out.append(f"- line: {n['lineno']}")
        if n.get("docstring"):
            ds0 = n["docstring"].strip().splitlines()[0]
            out.append(f"- doc: {ds0[:140]}")
        if n.get("snippet"):
            sn = n["snippet"]
            out.append("")
            out.append(f"```python\n{sn['text']}\n```")
        out.append("")

    out.append("\n---\n")
    out.append("## Edges\n")
    for e in pack["edges"]:
        out.append(f"- `{e['src']}` -[{e['rel']}]-> `{e['dst']}`")
    out.append("")
    return "\n".join(out)


def build_pack(
    *,
    repo_root: Path,
    sqlite_path: Path,
    lancedb_dir: Path,
    table: str,
    query: str,
    k: int,
    hop: int,
    rels: Sequence[str],
    include_symbols: bool,
    model_name: str,
    context: int,
    max_lines: int,
    max_nodes: int,
) -> dict:
    # --- semantic seeds (ranking source) ---
    hits = lancedb_vector_search(lancedb_dir, table, query, k, model_name=model_name)

    # LanceDB commonly returns a distance/score field; handle both.
    # Smaller distance is better. If only score exists, convert to distance-like.
    seed_rank: Dict[str, dict] = {}
    for i, h in enumerate(hits):
        nid = h["id"]
        dist = None
        for key in ("_distance", "distance"):
            if key in h and h[key] is not None:
                dist = float(h[key])
                break
        if dist is None and ("score" in h and h["score"] is not None):
            # Higher score better -> invert to distance-like
            dist = 1.0 / (1.0 + float(h["score"]))
        if dist is None:
            dist = float(i)  # deterministic fallback

        seed_rank[nid] = {"rank": i, "dist": dist}

    seed_ids = set(seed_rank.keys())

    con = sqlite3.connect(str(sqlite_path))

    # --- provenance-aware graph expansion ---
    meta = expand_with_provenance(con, seed_ids, hop=hop, rels=rels)

    # --- materialize nodes ---
    all_ids = set(meta.keys())
    raw_nodes: List[dict] = []

    for nid in sorted(all_ids):
        n = fetch_node(con, nid)
        if not n:
            continue
        if (not include_symbols) and n["kind"] == "symbol":
            continue

        # ranking features
        best_hop = meta[nid]["best_hop"]
        via_seed = meta[nid]["via_seed"]
        # seed distance: seeds have real dist, non-seeds inherit via_seed dist
        base_dist = seed_rank.get(via_seed, {"dist": 1e9})["dist"]

        # Deterministic overall score: hop dominates; dist breaks ties
        # Smaller is better.
        n["_rank_key"] = (best_hop, base_dist, n["kind"], n["id"])
        n["_best_hop"] = best_hop
        n["_via_seed"] = via_seed
        n["_seed_dist"] = base_dist

        raw_nodes.append(n)

    # --- attach spans early (for dedupe) ---
    # We compute spans from file lines; cache per file.
    file_cache: Dict[str, List[str]] = {}

    for n in raw_nodes:
        mp = n.get("module_path")
        if not mp:
            n["_span"] = None
            continue

        src_path = safe_join(repo_root, mp)
        if mp not in file_cache:
            file_cache[mp] = read_lines(src_path)
        lines = file_cache[mp]

        start, end = compute_span(
            n["kind"],
            n.get("lineno"),
            n.get("end_lineno"),
            context=context,
            max_lines=max_lines,
            file_nlines=len(lines),
        )
        n["_span"] = (start, end)

    # --- rank nodes (best first) ---
    raw_nodes.sort(key=lambda x: x["_rank_key"])

    # --- dedupe by file+overlapping span ---
    kept: List[dict] = []
    kept_by_file: Dict[str, List[Tuple[Tuple[int, int], str]]] = {}  # span -> node_id

    for n in raw_nodes:
        if len(kept) >= max_nodes:
            break

        mp = n.get("module_path") or ""
        span = n.get("_span")

        # If no span, keep only if not too many already (rare)
        if not mp or not span or span[1] < span[0]:
            kept.append(n)
            continue

        overlaps = False
        for s2, _nid2 in kept_by_file.get(mp, []):
            if spans_overlap(span, s2, gap=2):
                overlaps = True
                break

        if overlaps:
            continue

        kept.append(n)
        kept_by_file.setdefault(mp, []).append((span, n["id"]))

    kept_ids = {n["id"] for n in kept}

    # --- edges within kept set ---
    edges = edges_within_set(con, kept_ids)

    # --- attach snippets now (only for kept) ---
    for n in kept:
        mp = n.get("module_path")
        span = n.get("_span")
        if not mp or not span:
            continue
        lines = file_cache.get(mp)
        if lines is None:
            src_path = safe_join(repo_root, mp)
            lines = read_lines(src_path)
            file_cache[mp] = lines

        start, end = span
        if end >= start and lines:
            n["snippet"] = make_snippet(mp, lines, start, end)

    con.close()

    # strip internal keys before returning
    for n in kept:
        for k in list(n.keys()):
            if k.startswith("_"):
                del n[k]

    return {
        "query": query,
        "seeds": len(seed_ids),
        "expanded_nodes": len(all_ids),
        "returned_nodes": len(kept),
        "hop": hop,
        "rels": list(rels),
        "include_symbols": include_symbols,
        "model": model_name,
        "nodes": kept,
        "edges": edges,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--repo-root",
        required=True,
        help="Root of the source tree used to build the KG (for snippets)",
    )
    p.add_argument("--sqlite", required=True, help="Path to codekg.sqlite")
    p.add_argument("--lancedb", required=True, help="LanceDB directory")
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
        default="CONTAINS,CALLS,IMPORTS,INHERITS",
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
    p.add_argument(
        "--max-lines", type=int, default=160, help="Max lines per snippet block"
    )
    p.add_argument(
        "--max-nodes",
        type=int,
        default=50,
        help="Max nodes returned in pack (deterministic truncation)",
    )
    p.add_argument(
        "--format", choices=["json", "md"], default="md", help="Output format"
    )
    p.add_argument("--out", default="", help="Output path (default: stdout)")
    args = p.parse_args()

    rels = tuple(r.strip() for r in args.rels.split(",") if r.strip())

    pack = build_pack(
        repo_root=Path(args.repo_root),
        sqlite_path=Path(args.sqlite),
        lancedb_dir=Path(args.lancedb),
        table=args.table,
        query=args.q,
        k=args.k,
        hop=args.hop,
        rels=rels,
        include_symbols=args.include_symbols,
        model_name=args.model,
        context=args.context,
        max_lines=args.max_lines,
        max_nodes=args.max_nodes,
    )

    if args.format == "json":
        text = json.dumps(pack, indent=2, ensure_ascii=False)
    else:
        text = to_markdown(pack)

    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"OK: wrote {args.format} to {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
