#!/usr/bin/env python3
"""
mcp_server.py — CodeKG MCP Server

Exposes the CodeKG hybrid query and snippet-pack pipeline as
Model Context Protocol (MCP) tools, allowing any MCP-compatible
agent (Claude Desktop, Cursor, Continue, etc.) to query a codebase
knowledge graph directly.

Tools
-----
query_codebase(q, k, hop, rels, include_symbols)
    Hybrid semantic + structural query.  Returns ranked nodes and
    edges as a JSON string.

pack_snippets(q, k, hop, rels, include_symbols, context, max_lines, max_nodes)
    Hybrid query + source-grounded snippet extraction.  Returns a
    Markdown context pack suitable for direct LLM ingestion.

get_node(node_id)
    Fetch a single node by its stable ID.  Returns JSON.

graph_stats()
    Return node and edge counts by kind/relation.  Returns JSON.

Usage
-----
Install the package, then run::

    codekg-mcp --repo /path/to/repo --db .codekg/graph.sqlite --lancedb .codekg/lancedb

Or configure in Claude Desktop's ``claude_desktop_config.json``::

    {
      "mcpServers": {
        "codekg": {
          "command": "codekg-mcp",
          "args": [
            "--repo", "/path/to/repo",
            "--db",   "/path/to/repo/.codekg/graph.sqlite",
            "--lancedb", "/path/to/repo/.codekg/lancedb"
          ]
        }
      }
    }

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Lazy MCP import — mcp is an optional dependency; give a clear error if absent
# ---------------------------------------------------------------------------

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print(
        "ERROR: 'mcp' package not found.\n"
        "Install it with:  pip install mcp\n"
        "Or add it to your project:  poetry add mcp",
        file=sys.stderr,
    )
    sys.exit(1)

from code_kg import CodeKG
from code_kg.store import DEFAULT_RELS

# ---------------------------------------------------------------------------
# Global state — initialised in main() before the server starts
# ---------------------------------------------------------------------------

_kg: CodeKG | None = None


def _get_kg() -> CodeKG:
    if _kg is None:
        raise RuntimeError(
            "CodeKG not initialised.  "
            "Run the server via 'codekg-mcp --repo ... --db ... --lancedb ...'"
        )
    return _kg


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "codekg",
    instructions=(
        "CodeKG gives you precise, source-grounded answers about a Python codebase. "
        "Use query_codebase for structural exploration and pack_snippets when you need "
        "actual source code to reason about. Always prefer pack_snippets when you need "
        "to understand implementation details."
    ),
)


@mcp.tool()
def query_codebase(
    q: str,
    k: int = 8,
    hop: int = 1,
    rels: str = "CONTAINS,CALLS,IMPORTS,INHERITS",
    include_symbols: bool = False,
    max_nodes: int = 25,
) -> str:
    """
    Hybrid semantic + structural query over the codebase knowledge graph.

    Performs vector-similarity seeding followed by graph expansion to return
    a ranked set of relevant nodes (modules, classes, functions, methods) and
    the edges between them.

    :param q: Natural-language query, e.g. "database connection setup".
    :param k: Number of semantic seed nodes (default 8).
    :param hop: Graph expansion hops from each seed (default 1).
    :param rels: Comma-separated edge types to follow
                 (CONTAINS, CALLS, IMPORTS, INHERITS).
    :param include_symbols: Include low-level symbol nodes (default False).
    :param max_nodes: Maximum nodes to return (default 25).
    :return: JSON string with keys: query, seeds, expanded_nodes,
             returned_nodes, hop, rels, nodes, edges.
    """
    rel_tuple = tuple(r.strip() for r in rels.split(",") if r.strip())
    result = _get_kg().query(
        q,
        k=k,
        hop=hop,
        rels=rel_tuple or DEFAULT_RELS,
        include_symbols=include_symbols,
        max_nodes=max_nodes,
    )
    return result.to_json()


@mcp.tool()
def pack_snippets(
    q: str,
    k: int = 8,
    hop: int = 1,
    rels: str = "CONTAINS,CALLS,IMPORTS,INHERITS",
    include_symbols: bool = False,
    context: int = 5,
    max_lines: int = 60,
    max_nodes: int = 15,
) -> str:
    """
    Hybrid query + source-grounded snippet extraction.

    Returns a Markdown context pack containing ranked, deduplicated code
    snippets with line numbers — ready for direct LLM ingestion.

    :param q: Natural-language query, e.g. "configuration loading".
    :param k: Number of semantic seed nodes (default 8).
    :param hop: Graph expansion hops (default 1).
    :param rels: Comma-separated edge types to follow.
    :param include_symbols: Include symbol nodes (default False).
    :param context: Extra context lines around each definition (default 5).
    :param max_lines: Maximum lines per snippet block (default 60).
    :param max_nodes: Maximum nodes to include in the pack (default 15).
    :return: Markdown string with source-grounded code snippets.
    """
    rel_tuple = tuple(r.strip() for r in rels.split(",") if r.strip())
    pack = _get_kg().pack(
        q,
        k=k,
        hop=hop,
        rels=rel_tuple or DEFAULT_RELS,
        include_symbols=include_symbols,
        context=context,
        max_lines=max_lines,
        max_nodes=max_nodes,
    )
    return pack.to_markdown()


@mcp.tool()
def get_node(node_id: str) -> str:
    """
    Fetch a single node by its stable ID.

    Node IDs follow the pattern ``<kind>:<module_path>:<qualname>``,
    e.g. ``fn:src/code_kg/store.py:GraphStore.expand``.

    :param node_id: Stable node identifier.
    :return: JSON string with node fields, or an error message.
    """
    node = _get_kg().node(node_id)
    if node is None:
        return json.dumps({"error": f"Node not found: {node_id!r}"})
    return json.dumps(node, indent=2, ensure_ascii=False)


@mcp.tool()
def graph_stats() -> str:
    """
    Return node and edge counts broken down by kind and relation.

    Useful for understanding the size and shape of the knowledge graph
    before issuing queries.

    :return: JSON string with total_nodes, total_edges, node_counts,
             edge_counts, and db_path.
    """
    stats = _get_kg().stats()
    return json.dumps(stats, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="codekg-mcp",
        description="CodeKG MCP server — exposes codebase query tools to AI agents.",
    )
    p.add_argument(
        "--repo",
        default=".",
        help="Repository root directory (default: current directory)",
    )
    p.add_argument(
        "--db",
        default=".codekg/graph.sqlite",
        help="Path to the SQLite knowledge graph (default: .codekg/graph.sqlite)",
    )
    p.add_argument(
        "--lancedb",
        default=".codekg/lancedb",
        help="Path to the LanceDB vector index directory (default: .codekg/lancedb)",
    )
    p.add_argument(
        "--model",
        default="all-MiniLM-L6-v2",
        help="Sentence-transformer model name (default: all-MiniLM-L6-v2)",
    )
    p.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport: stdio (default, for Claude Desktop) or sse (HTTP)",
    )
    return p.parse_args(argv)


def main(argv: list | None = None) -> None:
    """
    CLI entry point for the CodeKG MCP server.

    Initialises the CodeKG instance and starts the MCP server using the
    requested transport (stdio for Claude Desktop, sse for HTTP clients).
    """
    global _kg

    args = _parse_args(argv)

    repo = Path(args.repo).resolve()
    db = Path(args.db) if Path(args.db).is_absolute() else repo / args.db
    lancedb_dir = Path(args.lancedb) if Path(args.lancedb).is_absolute() else repo / args.lancedb

    if not db.exists():
        print(
            f"WARNING: SQLite database not found at '{db}'.\n"
            "Run 'codekg-build-sqlite' and 'codekg-build-lancedb' first.",
            file=sys.stderr,
        )

    print(
        f"CodeKG MCP server starting\n"
        f"  repo     : {repo}\n"
        f"  db       : {db}\n"
        f"  lancedb  : {lancedb_dir}\n"
        f"  model    : {args.model}\n"
        f"  transport: {args.transport}",
        file=sys.stderr,
    )

    _kg = CodeKG(
        repo_root=repo,
        db_path=db,
        lancedb_dir=lancedb_dir,
        model=args.model,
    )

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
