# CodeKG Architecture (Condensed)

**CodeKG v0** — Deterministic knowledge graph for Python codebases via static analysis, SQLite persistence, and semantic search acceleration.

## Core Design

1. **Structure is authoritative** — AST-derived graph is ground truth
2. **Semantics accelerate, never decide** — Vector embeddings seed/rank, never invent
3. **Everything traceable** — Nodes/edges map to concrete file:lineno
4. **Deterministic** — Identical input → identical output
5. **Composable** — SQLite (structure), LanceDB (vectors), Markdown/JSON (export)

## Layered Architecture

```
CodeKG (orchestrator)
  ├─ CodeGraph (pure AST extraction, no I/O)
  ├─ GraphStore (SQLite: nodes/edges persistence + BFS)
  ├─ SemanticIndex (LanceDB: embeddings, disposable)
  └─ codekg.py (locked v0 primitives: Node, Edge, extract_repo)
```

### Layer 1: Primitives (`codekg.py`)
- **Node**: frozen dataclass (id, kind, name, qualname, module_path, lineno, docstring)
- **Edge**: frozen dataclass (src, rel, dst, evidence)
- **extract_repo()**: walks .py files, two AST passes (defs + calls), returns (nodes, edges)
- Node kinds: `module`, `class`, `function`, `method`, `symbol`
- Edge relations: `CONTAINS`, `CALLS`, `IMPORTS`, `INHERITS`, `RESOLVES_TO`

### Layer 2: CodeGraph (`graph.py`)
Pure AST extraction with lazy evaluation. No persistence, no embeddings.
- `extract()`: cached, force=True to re-run
- `.nodes`, `.edges`: trigger extraction on first access
- `stats()`: node/edge counts by kind

### Layer 3: GraphStore (`store.py`)
SQLite-backed authoritative store. No embeddings, no AST.

**Key methods:**
- `write(nodes, edges, wipe=False)`: persist graph (upsert)
- `node(id)`: fetch single node by ID
- `query_nodes(kinds=, module=)`: filtered list
- `edges_within(node_ids)`: edges with both endpoints in set
- `expand(seed_ids, hop=N, rels=…)`: BFS → Dict[id, ProvMeta]
- `resolve_symbols()`: post-build; adds RESOLVES_TO from sym: stubs to definitions
- `callers_of(node_id)`: two-phase reverse lookup (direct + via sym: stubs)

**ProvMeta** (from expand): `best_hop`, `via_seed`

### Layer 4: SemanticIndex (`index.py`)
LanceDB-backed vector index. Derived, disposable, rebuildable.

**Embedder** abstract interface:
- `embed_texts(texts)` → List[List[float]]
- `embed_query(query)` → List[float]

**SentenceTransformerEmbedder**: default impl using sentence-transformers

**SeedHit**: id, kind, name, qualname, module_path, distance, rank

Index text format: KIND, NAME, QUALNAME, MODULE, LINE, DOCSTRING

## Orchestrator: CodeKG (`kg.py`)

Owns all four layers with lazy initialization.

```python
kg = CodeKG(repo_root, db_path, lancedb_dir, model, table)
kg.build(wipe=True)           # full pipeline
kg.build_graph(wipe=True)     # AST → SQLite only
kg.build_index(wipe=True)     # SQLite → LanceDB only
kg.query(q, k=8, hop=1)       # → QueryResult
kg.pack(q, k=8, hop=1)        # → SnippetPack (with snippets)
kg.callers(node_id)           # → List[dict]
kg.stats()                    # BuildStats
kg.node(node_id)              # fetch node
```

**Result types:**
- **BuildStats**: repo_root, db_path, total_nodes, total_edges, node_counts, edge_counts, indexed_rows?, index_dim?
- **QueryResult**: query, seeds, expanded_nodes, returned_nodes, hop, rels, nodes[], edges[]
- **SnippetPack**: extends QueryResult, adds source snippets with path/start/end/text

## Build Pipeline

### Phase 1: Static Analysis (AST → SQLite)
1. Walk .py files (skip .venv, __pycache__, .git)
2. Pass 1: extract modules, classes, functions, methods, imports, inheritance
3. Pass 2: extract call graph (honest; unresolved → sym: stubs)
4. Generate stable node IDs: `mod:`, `cls:`, `fn:`, `m:`, `sym:`
5. Emit edges with evidence (lineno, expr)
6. Persist to SQLite (upsert, idempotent)
7. `resolve_symbols()`: name-match sym: stubs to first-party defs, write RESOLVES_TO edges

### Phase 2: Semantic Indexing (SQLite → LanceDB)
- Read module/class/function/method nodes
- Build canonical index text (name + qualname + module + docstring)
- Embed in batches via SentenceTransformerEmbedder
- Upsert to LanceDB (delete-then-add per batch)

## Hybrid Query Model

### Phase 1: Semantic Seeding
```
query → embed → vector search → top-K SeedHit list
```

### Phase 2: Structural Expansion
```
seed_ids → GraphStore.expand(hop=N) → Dict[id, ProvMeta]
```
BFS over CONTAINS, CALLS, IMPORTS, INHERITS. Each node records best_hop and via_seed.

## Ranking & Deduplication

Composite key: `(best_hop, seed_distance, kind_priority, node_id)`
Kind priority: function=0, method=1, class=2, module=3, symbol=4

**Deduplication** (pack only):
- Compute source span (start, end) per node
- Skip overlapping spans (2-line gap) in same file
- Cap at max_nodes (default 50)

## Snippet Extraction

For each retained node:
1. Resolve module_path → absolute path (path-traversal safe)
2. Read file lines (cached per file)
3. Compute span: AST lineno/end_lineno ± context lines, capped at max_lines
4. Emit line-numbered text block

## Interfaces

### Streamlit Web App (`codekg-viz`)
Three tabs:
- **Graph Browser**: pyvis interactive graph, filter by kind/module, detail panels
- **Hybrid Query**: query → seeds → expansion → ranked results (graph/table/edge/JSON views)
- **Snippet Pack**: query → source-grounded snippets (MD/JSON download)

Sidebar: Build Graph, Build Index, Build All controls

### MCP Server (`mcp_server.py`)
Thin wrapper around CodeKG, stateful (one instance per process).

**Tools:**
- `query_codebase(q, k, hop, rels, include_symbols)` → JSON
- `pack_snippets(q, k, hop, rels, include_symbols, context, max_lines, max_nodes)` → Markdown
- `callers(node_id, rel)` → JSON (caller_count + callers list)
- `get_node(node_id)` → JSON
- `graph_stats()` → JSON

**Start:** `codekg-mcp --repo /path --db .codekg/graph.sqlite --lancedb .codekg/lancedb`

### CLI Entry Points
- `codekg-build-sqlite`: repo → SQLite
- `codekg-build-lancedb`: SQLite → LanceDB
- `codekg-query`: hybrid query, text output
- `codekg-pack`: hybrid query + snippet pack
- `codekg-viz`: launch Streamlit app
- `codekg-mcp`: start MCP server

### `/setup-mcp` Claude Skill
Automates full MCP setup: resolve repo → verify install → build SQLite → build LanceDB → smoke test → configure .mcp.json + claude_desktop_config.json

## Source Layout
```
code_kg/src/code_kg/
  ├── codekg.py              # Primitives
  ├── graph.py               # CodeGraph
  ├── store.py               # GraphStore
  ├── index.py               # SemanticIndex
  ├── kg.py                  # CodeKG orchestrator
  ├── build_codekg_sqlite.py # CLI
  ├── build_codekg_lancedb.py
  ├── codekg_query.py
  ├── codekg_snippet_packer.py
  ├── codekg_viz.py
  ├── app.py                 # Streamlit app
  └── mcp_server.py          # MCP server
```

## Data Flow

```
.py files
  ↓ CodeGraph.extract()
(nodes, edges) — pure, deterministic
  ↓ GraphStore.write()
.sqlite — authoritative, canonical
  ├─ nodes table
  └─ edges table
  ↓ resolve_symbols()
RESOLVES_TO edges — sym: → fn:/cls:/m:
  ↓ SemanticIndex.build()
.lancedb — derived, disposable
  ├─ id
  ├─ vector
  └─ metadata
  ↓ CodeKG.query() / .pack()
semantic seeds (LanceDB) + structural expansion (SQLite)
  ↓ rank + dedupe
QueryResult / SnippetPack
  ↓
Markdown / JSON
  ├→ Streamlit (codekg-viz)
  └→ MCP server (mcp_server.py)
```

## Dependencies
- `lancedb ≥ 0.6.0`: vector database
- `sentence-transformers ≥ 2.7.0`: embedder
- `numpy ≥ 1.24.0`: vector ops
- `streamlit ≥ 1.35.0`: web app
- `pyvis ≥ 0.3.2`: graph viz
- `pandas ≥ 2.0.0`: tables
- `mcp ≥ 1.0.0` (optional): MCP server
- Python `ast`, `sqlite3` (stdlib)

Python ≥ 3.10, < 3.13
