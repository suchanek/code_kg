CodeKG Architecture - A Deterministic Knowledge Graph for Python Codebases

Author: Eric G. Suchanek, PhD

OVERVIEW

CodeKG constructs a knowledge graph from Python codebases using static analysis. The graph captures structural relationships — definitions, calls, imports, inheritance — directly from the Python AST, stores them in SQLite, and augments retrieval with vector embeddings via LanceDB. Structure is treated as ground truth; semantic search is an acceleration layer. Every node and edge maps to a concrete file and line number.

The system ships with: a Python library with layered class API, CLI entry points, a Streamlit web application (codekg-viz), an MCP server (codekg-mcp), and a /setup-mcp Claude skill.

DESIGN PRINCIPLES

Structure is authoritative. Semantics accelerate, never decide. Everything is traceable. Determinism over heuristics. Composable artifacts (SQLite + LanceDB + Markdown/JSON).

LAYERED ARCHITECTURE

Four focused layers: codekg.py (primitives), graph.py (CodeGraph), store.py (GraphStore), index.py (SemanticIndex).

Layer 1 — Primitives (codekg.py): Node is a frozen dataclass (id, kind, name, qualname, module_path, lineno, end_lineno, docstring). Edge is a frozen dataclass (src, rel, dst, evidence). extract_repo(repo_root) walks .py files, runs two AST passes, returns (nodes, edges). Node kinds: module, class, function, method, symbol. Edge relations: CONTAINS, CALLS, IMPORTS, INHERITS, RESOLVES_TO.

Layer 2 — CodeGraph (graph.py): Pure AST extraction, no I/O or persistence. graph.extract() with lazy evaluation and force=True to re-run. Properties: nodes, edges, result(). stats() returns counts by kind.

Layer 3 — GraphStore (store.py): SQLite-backed authoritative store. write(nodes, edges, wipe=False), node(id), query_nodes(kinds=, module=), edges_within(node_ids), expand(seed_ids, hop=1, rels=…) returning ProvMeta dict, resolve_symbols() for post-build symbol resolution, callers_of(node_id) for two-phase reverse lookup, stats(). ProvMeta contains best_hop and via_seed.

Layer 4 — SemanticIndex (index.py): LanceDB-backed vector index, disposable and rebuildable. Pluggable Embedder interface (embed_texts, embed_query). SentenceTransformerEmbedder is default. SeedHit dataclass contains id, kind, name, qualname, module_path, distance, rank.

ORCHESTRATOR — CodeKG (kg.py)

Top-level entry point owning all four layers with lazy initialization. Methods: build(wipe=True) for full pipeline, build_graph(wipe=True) for AST→SQLite, build_index(wipe=True) for SQLite→LanceDB, query(q, k=8, hop=1) returning QueryResult, pack(q, k=8, hop=1) returning SnippetPack, callers(node_id) for reverse lookup, stats(), node(id). Supports context manager.

RESULT TYPES

BuildStats: repo_root, db_path, total_nodes, total_edges, node_counts dict, edge_counts dict, indexed_rows, index_dim.

QueryResult: query, seeds, expanded_nodes, returned_nodes, hop, rels, nodes list, edges list.

SnippetPack: extends QueryResult with source snippets (path, start, end, text).

BUILD PIPELINE

Phase 1 — Static Analysis (AST→SQLite): Walk .py files (skip .venv, __pycache__, .git). Pass 1 extracts modules, classes, functions, methods, imports, inheritance. Pass 2 extracts call graph; unresolved calls become sym: nodes. Generate stable node IDs (mod:, cls:, fn:, m:, sym:) with evidence (lineno, expr). Persist via upsert (idempotent). GraphStore.resolve_symbols() automatically name-matches sym: stubs to first-party defs and writes RESOLVES_TO edges, enabling fan-in queries across module boundaries.

Phase 2 — Semantic Indexing (SQLite→LanceDB): Read module/class/function/method nodes, build canonical index text (name + qualname + module + docstring), embed in batches via SentenceTransformerEmbedder, upsert to LanceDB (delete-then-add per batch). Vector index is derived and disposable.

HYBRID QUERY MODEL

query() and pack() execute in two phases. Phase 1 — Semantic Seeding: query string → embed → vector search → top-K SeedHit list (id, distance, rank). Phase 2 — Structural Expansion: seed_ids → GraphStore.expand(hop=N) → BFS over CONTAINS/CALLS/IMPORTS/INHERITS edges, recording best_hop and via_seed for each node.

RANKING AND DEDUPLICATION

Rank by composite key: (best_hop, seed_distance, kind_priority, node_id). Kind priority: function=0, method=1, class=2, module=3, symbol=4. pack() deduplicates by source span (start_line, end_line), skipping overlapping spans (2-line gap) in same file, capping at max_nodes (default 50).

INTERFACES

Streamlit App (codekg-viz): Graph Browser (pyvis interactive graph with filtering), Hybrid Query (natural language query with semantic seeds + graph expansion), Snippet Pack (query with source snippets). Sidebar: Build Graph, Build Index, Build All controls. Reads CODEKG_DB and CODEKG_LANCEDB env vars.

MCP Server (codekg-mcp): Thin wrapper around CodeKG. Start: codekg-mcp --repo /path --db .codekg/graph.sqlite --lancedb .codekg/lancedb. Flags: --repo (.), --db, --lancedb, --model (all-MiniLM-L6-v2), --transport (stdio/sse). Tools: query_codebase(q, k, hop, rels, include_symbols), pack_snippets(...), callers(node_id, rel), get_node(node_id), graph_stats(). Optional dependency: pip install "code-kg[mcp]".

/setup-mcp Claude Skill: Automates setup. Resolves repo → verifies CodeKG → builds SQLite → builds LanceDB → smoke-tests → configures .mcp.json + claude_desktop_config.json.

CLI ENTRY POINTS

codekg-build-sqlite, codekg-build-lancedb, codekg-query, codekg-pack, codekg-viz, codekg-mcp. Each is a thin wrapper.

SOURCE LAYOUT

code_kg/src/code_kg/: codekg.py (primitives), graph.py (CodeGraph), store.py (GraphStore), index.py (SemanticIndex), kg.py (orchestrator), build_*.py (CLI wrappers), app.py (Streamlit), mcp_server.py. Tests: test_primitives.py (40), test_graph.py (12), test_store.py (18), test_kg.py (28). Docs: Architecture.md, MCP.md.

DATA FLOW

.py files → CodeGraph.extract() → (nodes, edges) → GraphStore.write() → .sqlite (authoritative) → resolve_symbols() → RESOLVES_TO edges → SemanticIndex.build() → .lancedb (derived, disposable) → CodeKG.query()/pack() → semantic seeds + structural expansion → rank + dedupe → QueryResult/SnippetPack → Markdown/JSON → Streamlit (codekg-viz) or MCP server.

DEPENDENCIES

Core: lancedb (0.6.0+), sentence-transformers (2.7.0+), numpy (1.24.0+), streamlit (1.35.0+), pyvis (0.3.2+), pandas (2.0.0+). Optional: mcp (1.0.0+). Stdlib: ast, sqlite3. Python 3.10-3.12.
