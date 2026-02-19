"""
code_kg: A tool to build a searchable knowledge graph from Python repositories.

Pure AST extraction → SQLite (authoritative) → LanceDB (semantic index).

Public API
----------
Primary entry point::

    from code_kg import CodeKG

    kg = CodeKG(repo_root, db_path, lancedb_dir)
    stats = kg.build(wipe=True)
    result = kg.query("database connection setup")
    pack = kg.pack("configuration loading")
    pack.save("context.md")

Individual layers::

    from code_kg import CodeGraph, GraphStore, SemanticIndex

Result types::

    from code_kg import BuildStats, QueryResult, SnippetPack, Snippet

Low-level primitives (v0 contract, locked)::

    from code_kg import Node, Edge
"""

__version__ = "0.1.0"
__author__ = "Eric G. Suchanek, PhD"

# Low-level primitives (locked v0 contract)
from code_kg.codekg import Edge, Node

# Layered classes
from code_kg.graph import CodeGraph
from code_kg.store import DEFAULT_RELS, GraphStore, ProvMeta
from code_kg.index import Embedder, SemanticIndex, SeedHit, SentenceTransformerEmbedder

# Orchestrator + result types
from code_kg.kg import BuildStats, CodeKG, QueryResult, Snippet, SnippetPack

__all__ = [
    # primitives
    "Node",
    "Edge",
    # layers
    "CodeGraph",
    "GraphStore",
    "ProvMeta",
    "DEFAULT_RELS",
    "Embedder",
    "SentenceTransformerEmbedder",
    "SemanticIndex",
    "SeedHit",
    # orchestrator
    "CodeKG",
    # result types
    "BuildStats",
    "QueryResult",
    "Snippet",
    "SnippetPack",
]
