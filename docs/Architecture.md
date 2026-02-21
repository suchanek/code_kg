# CodeKG Architecture

**CodeKG v0** — A Deterministic Knowledge Graph for Python Codebases
with Semantic Indexing and Source-Grounded Snippet Packing

*Author: Eric G. Suchanek, PhD*

---

## Overview

CodeKG constructs a deterministic, explainable knowledge graph from a Python codebase using static analysis. The graph captures structural relationships — definitions, calls, imports, and inheritance — directly from the Python AST, stores them in SQLite, and augments retrieval with vector embeddings via LanceDB.

Structure is treated as **ground truth**. Semantic search is strictly an acceleration layer. Every node and edge maps to a concrete file and line number.

The system ships with:
- A **Python library** (`code_kg`) with a layered class API
- **CLI entry points** for building and querying the graph
- A **Streamlit web application** (`app.py`) for interactive exploration
- A **Docker image** for zero-install deployment
- An **MCP server** (`codekg-mcp`) for AI agent integration
- A **`/setup-mcp` Claude skill** for automated MCP configuration

---

## Design Principles

1. **Structure is authoritative** — The AST-derived graph is the source of truth.
2. **Semantics accelerate, never decide** — Vector embeddings seed and rank retrieval but never invent structure.
3. **Everything is traceable** — Nodes and edges map to concrete files and line numbers.
4. **Determinism over heuristics** — Identical input yields identical output.
5. **Composable artifacts** — SQLite for structure, LanceDB for vectors, Markdown/JSON for consumption.

---

## Layered Class Architecture

The system is organized into four focused layers, each independently testable and composable:

```
┌─────────────────────────────────────────────────────────┐
│                      CodeKG                             │
│              (orchestrator — kg.py)                     │
│                                                         │
│  build()  build_graph()  build_index()                  │
│  query()  pack()  stats()  node()                       │
└────────┬──────────────┬──────────────┬──────────────────┘
         │              │              │
         ▼              ▼              ▼
  ┌────────────┐ ┌────────────┐ ┌──────────────────┐
  │ CodeGraph  │ │ GraphStore │ │  SemanticIndex   │
  │ (graph.py) │ │ (store.py) │ │   (index.py)     │
  │            │ │            │ │                  │
  │ Pure AST   │ │  SQLite    │ │  LanceDB +       │
  │ extraction │ │ canonical  │ │  Embedder        │
  │ No I/O     │ │ store      │ │  (disposable)    │
  └─────┬──────┘ └────────────┘ └──────────────────┘
        │
        ▼
  ┌────────────┐
  │  codekg.py │
  │ (primitives│
  │  locked v0)│
  │ Node, Edge │
  │ extract_   │
  │   repo()   │
  └────────────┘
```

### Layer 1 — Primitives (`codekg.py`)

The locked v0 contract. Pure, deterministic, side-effect free.

- **`Node`** — frozen dataclass: `id`, `kind`, `name`, `qualname`, `module_path`, `lineno`, `end_lineno`, `docstring`
- **`Edge`** — frozen dataclass: `src`, `rel`, `dst`, `evidence`
- **`extract_repo(repo_root)`** — walks all `.py` files, runs two AST passes (definitions + call graph), returns `(nodes, edges)`

Node kinds: `module`, `class`, `function`, `method`, `symbol`
Edge relations: `CONTAINS`, `CALLS`, `IMPORTS`, `INHERITS`

### Layer 2 — `CodeGraph` (`graph.py`)

Pure AST extraction with a clean object interface. No I/O, no persistence.

```python
graph = CodeGraph("/path/to/repo")
graph.extract()          # cached; force=True to re-run
nodes = graph.nodes      # List[Node]
edges = graph.edges      # List[Edge]
nodes, edges = graph.result()
print(graph.stats())     # node/edge counts by kind
```

- Lazy extraction — `.nodes` and `.edges` trigger `extract()` automatically
- `extract(force=True)` re-runs from scratch
- `stats()` returns counts by kind/relation plus `repo_root`

### Layer 3 — `GraphStore` (`store.py`)

SQLite-backed authoritative store. No embeddings, no AST.

```python
store = GraphStore("codekg.sqlite")
store.write(nodes, edges, wipe=True)   # persist graph
n = store.node("fn:src/foo.py:bar")    # fetch by id
nodes = store.query_nodes(kinds=["function", "method"])
edges = store.edges_within(node_id_set)
meta  = store.expand(seed_ids, hop=2)  # → Dict[str, ProvMeta]
print(store.stats())
```

Key methods:

| Method | Description |
|---|---|
| `write(nodes, edges, wipe=False)` | Persist a complete graph (upsert) |
| `clear()` | Delete all nodes and edges |
| `node(id)` | Fetch a single node dict by ID |
| `query_nodes(kinds=, module=)` | Filtered node list |
| `edges_within(node_ids)` | Edges with both endpoints in the set |
| `expand(seed_ids, hop=1, rels=…)` | BFS expansion with `ProvMeta` provenance |
| `stats()` | Node/edge counts by kind/relation |

**`ProvMeta`** — returned by `expand()`:
- `best_hop` — minimum hop distance from any seed
- `via_seed` — ID of the seed that yielded the shortest path

Supports context manager (`with GraphStore(...) as store:`).

### Layer 4 — `SemanticIndex` (`index.py`)

LanceDB-backed vector index. Derived from SQLite; disposable and rebuildable.

```python
embedder = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
idx = SemanticIndex("./lancedb", embedder=embedder)
idx.build(store, wipe=True)            # embed nodes → LanceDB
hits = idx.search("database setup", k=8)  # → List[SeedHit]
```

**`Embedder`** — abstract base class with pluggable backends:
- `embed_texts(texts)` → `List[List[float]]`
- `embed_query(query)` → `List[float]` (default: calls `embed_texts`)

**`SentenceTransformerEmbedder`** — default implementation using `sentence-transformers`.

**`SeedHit`** — dataclass returned by `search()`:
- `id`, `kind`, `name`, `qualname`, `module_path`, `distance`, `rank`

Index text format (stable — changing invalidates the index):
```
KIND: function
NAME: connect_db
QUALNAME: DatabaseManager.connect_db
MODULE: src/db/manager.py
LINE: 42
DOCSTRING:
Establish a connection to the database.
```

---

## Orchestrator — `CodeKG` (`kg.py`)

The top-level entry point. Owns all four layers with lazy initialization.

```python
kg = CodeKG(
    repo_root="/path/to/repo",
    db_path="codekg.sqlite",
    lancedb_dir="./lancedb",
    model="all-MiniLM-L6-v2",   # optional
    table="codekg_nodes",        # optional
)

# Full pipeline
stats = kg.build(wipe=True)

# Graph only (no embedding)
stats = kg.build_graph(wipe=True)

# Index only (graph must exist)
stats = kg.build_index(wipe=True)

# Hybrid query
result = kg.query("database connection setup", k=8, hop=1)
result.print_summary()

# Snippet pack
pack = kg.pack("configuration loading", k=8, hop=1)
pack.save("context.md")          # or fmt="json"

# Convenience
kg.stats()                       # store stats
kg.node("fn:src/foo.py:bar")     # fetch node
```

Layer properties are lazy — the embedder and LanceDB connection are only created when first needed.

Supports context manager (`with CodeKG(...) as kg:`).

---

## Result Types (`kg.py`)

### `BuildStats`

Returned by `build()`, `build_graph()`, `build_index()`.

| Field | Type | Description |
|---|---|---|
| `repo_root` | `str` | Repository root |
| `db_path` | `str` | SQLite path |
| `total_nodes` | `int` | Total nodes in store |
| `total_edges` | `int` | Total edges in store |
| `node_counts` | `dict` | Counts by kind |
| `edge_counts` | `dict` | Counts by relation |
| `indexed_rows` | `int?` | Vectors indexed (None if not built) |
| `index_dim` | `int?` | Embedding dimension |

Methods: `to_dict()`, `__str__()`

### `QueryResult`

Returned by `kg.query()`.

| Field | Description |
|---|---|
| `query` | Original query string |
| `seeds` | Number of semantic seed nodes |
| `expanded_nodes` | Total nodes after graph expansion |
| `returned_nodes` | Nodes after symbol filtering |
| `hop` | Hop count used |
| `rels` | Edge types used |
| `nodes` | List of node dicts, sorted by rank |
| `edges` | Edges within the returned node set |

Methods: `to_dict()`, `to_json()`, `print_summary()`

### `SnippetPack`

Returned by `kg.pack()`. Extends `QueryResult` with source snippets.

Each node dict may contain a `snippet` key:
```json
{
  "path": "src/db/manager.py",
  "start": 40,
  "end": 55,
  "text": "   40: def connect_db(self):\n   41:     ..."
}
```

Methods: `to_dict()`, `to_json()`, `to_markdown()`, `save(path, fmt="md")`

---

## Build Pipeline

### Phase 1 — Static Analysis (AST → SQLite)

`CodeGraph.extract()` → `GraphStore.write()`

- Walk all `.py` files (skipping `.venv`, `__pycache__`, `.git`, etc.)
- **Pass 1**: extract modules, classes, functions, methods, imports, inheritance
- **Pass 2**: extract call graph (best-effort, honest — unresolved calls become `sym:` nodes)
- Generate stable, deterministic node IDs: `mod:`, `cls:`, `fn:`, `m:`, `sym:`
- Emit edges with evidence (`lineno`, `expr`)
- Persist to SQLite via upsert (idempotent)

**No embeddings. No LLMs.**

### Phase 2 — Semantic Indexing (SQLite → LanceDB)

`SemanticIndex.build(store)`

- Read `module`, `class`, `function`, `method` nodes from SQLite
- Build canonical index text (name + qualname + module + docstring)
- Embed in batches using `SentenceTransformerEmbedder`
- Upsert into LanceDB (delete-then-add per batch)

The vector index is **derived and disposable** — it can be rebuilt from SQLite at any time.

---

## Hybrid Query Model

`CodeKG.query()` and `CodeKG.pack()` execute in two phases:

### Phase 1 — Semantic Seeding

```
query string → embed → vector search → top-K SeedHit list
```

Each `SeedHit` carries `id`, `distance`, and `rank`.

### Phase 2 — Structural Expansion

```
seed_ids → GraphStore.expand(hop=N, rels=…) → Dict[node_id, ProvMeta]
```

BFS traversal over `CONTAINS`, `CALLS`, `IMPORTS`, `INHERITS` edges. Each reachable node records:
- `best_hop` — minimum distance from any seed
- `via_seed` — which seed yielded the shortest path

---

## Ranking and Deduplication

Nodes are ranked deterministically by a composite key:

```
(best_hop, seed_distance, kind_priority, node_id)
```

Kind priority: `function=0`, `method=1`, `class=2`, `module=3`, `symbol=4`

Deduplication (in `pack()` only):
- Compute source span `(start_line, end_line)` for each node
- Skip nodes whose span overlaps (within a 2-line gap) an already-kept span in the same file
- Cap total returned nodes at `max_nodes` (default 50)

---

## Snippet Extraction

For each retained node, `pack()` extracts a source-grounded snippet:

1. Resolve `module_path` → absolute path via `_safe_join()` (path-traversal safe)
2. Read file lines (cached per file)
3. Compute span: AST `lineno`/`end_lineno` ± `context` lines, capped at `max_lines`
4. Emit line-numbered text block

Module nodes show the top-of-file window. Nodes without line info fall back to the top window.

---

## Streamlit Web Application (`app.py`)

CodeKG ships an interactive knowledge-graph explorer built with **Streamlit** and **pyvis**.

```bash
# Launch locally
codekg-viz [--db codekg.sqlite] [--port 8501]

# Or directly
streamlit run app.py
```

The application provides three tabs:

| Tab | Description |
|---|---|
| **🗺️ Graph Browser** | Interactive pyvis graph of the full knowledge graph; filter by node kind or module path; click nodes for rich detail panels |
| **🔍 Hybrid Query** | Natural-language query → semantic seeds → graph expansion → ranked node results with graph, table, edge, and JSON views |
| **📦 Snippet Pack** | Query → source-grounded code snippets with download buttons for Markdown and JSON |

The sidebar exposes all build and query controls:
- **Build Graph** — AST extraction → SQLite (fast, no embeddings)
- **Build Index** — embed nodes → LanceDB
- **Build All** — full pipeline in one click

The app reads `CODEKG_DB` and `CODEKG_LANCEDB` environment variables so the Docker image works out of the box without manual path configuration.

---

## Docker Image

CodeKG ships a Docker image that packages the Streamlit app with all heavy dependencies (`sentence-transformers`, `lancedb`, `pyvis`, `torch`) into a single portable container.

```
┌─────────────────────────────────────────────────────────┐
│  Host machine                                           │
│                                                         │
│  /path/to/repo  ──(read-only)──▶  /workspace  ┐        │
│                                                │        │
│  Docker volume codekg-data ◀──────────────────┤        │
│    /data/codekg.sqlite                         │        │
│    /data/lancedb/                              │        │
│                                                │        │
│  localhost:8501 ◀──────────────────────────────┘        │
└─────────────────────────────────────────────────────────┘
```

### Quick Start

```bash
# Build
docker build -t codekg:latest .

# Run (analyse current directory)
docker run -p 8501:8501 \
  -v $(pwd):/workspace:ro \
  -v codekg-data:/data \
  codekg:latest
```

Open **http://localhost:8501** in your browser.

### Docker Compose (recommended)

```bash
# Start (build if needed, detached)
docker compose up -d

# Analyse a specific repo
REPO_ROOT=/path/to/your/repo docker compose up -d

# Use a different host port
CODEKG_PORT=8510 docker compose up -d

# Stop (volume preserved)
docker compose down

# Full reset (wipes graph data)
docker compose down -v
```

### Key Design Decisions

- **`python:3.11-slim`** base image — keeps the image small
- **Poetry 2.x** for reproducible dependency installation
- **Layer ordering** — `pyproject.toml`/`poetry.lock` copied before source files; source-only changes rebuild in seconds, not minutes
- **Named volume `codekg-data`** — SQLite graph and LanceDB index persist across container restarts
- **Read-only workspace mount** — the analysed repository is never modified

### Docker Files

| File | Purpose |
|---|---|
| `Dockerfile` | Image definition (python:3.11-slim + Poetry 2.x) |
| `docker-compose.yml` | Service orchestration with volumes, env vars, healthcheck |
| `.dockerignore` | Keeps build context lean |
| `.streamlit/config.toml` | Baked-in Streamlit server config (headless, dark theme) |

### Environment Variables

| Variable | Default (container) | Description |
|---|---|---|
| `CODEKG_DB` | `/data/codekg.sqlite` | SQLite knowledge graph path |
| `CODEKG_LANCEDB` | `/data/lancedb` | LanceDB vector index directory |
| `CODEKG_PORT` | `8501` | Host port (compose only) |
| `REPO_ROOT` | `./` | Host path mounted at `/workspace` (compose only) |

See `docs/docker.md` for the full Docker reference.

---

## MCP Server (`mcp_server.py`)

CodeKG ships a built-in **Model Context Protocol (MCP) server** that exposes the full hybrid query and snippet-pack pipeline as structured tools consumable by any MCP-compatible AI agent — Claude Desktop, Cursor, Continue, or any custom agent.

The server is a thin wrapper around `CodeKG`. It initialises a single `CodeKG` instance at startup and routes tool calls to it. All logic lives in the existing library; the MCP layer adds no logic of its own.

### Starting the Server

```bash
codekg-mcp \
  --repo    /path/to/repo \
  --db      /path/to/codekg.sqlite \
  --lancedb /path/to/lancedb
```

| Flag | Default | Description |
|---|---|---|
| `--repo` | `.` | Repository root (for snippet path resolution) |
| `--db` | `codekg.sqlite` | SQLite knowledge graph |
| `--lancedb` | `./lancedb` | LanceDB vector index directory |
| `--model` | `all-MiniLM-L6-v2` | Sentence-transformer embedding model |
| `--transport` | `stdio` | `stdio` (Claude Desktop) or `sse` (HTTP clients) |

### Prerequisites

The SQLite graph and LanceDB index must be built before starting the server:

```bash
codekg-build-sqlite --repo /path/to/repo --db codekg.sqlite
codekg-build-lancedb --db codekg.sqlite --lancedb ./lancedb
```

The `mcp` package is an optional dependency:

```bash
pip install "code-kg[mcp]"
# or
poetry add mcp
```

### Available Tools

| Tool | Description |
|---|---|
| `query_codebase(q, k, hop, rels, include_symbols)` | Hybrid semantic + structural query; returns ranked nodes and edges as JSON |
| `pack_snippets(q, k, hop, rels, include_symbols, context, max_lines, max_nodes)` | Hybrid query + source-grounded snippet extraction; returns Markdown |
| `get_node(node_id)` | Fetch a single node by its stable ID; returns JSON |
| `graph_stats()` | Node and edge counts by kind/relation; returns JSON |

### Configuring Claude Desktop

Add a `codekg` entry to `claude_desktop_config.json`
(macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "codekg": {
      "command": "codekg-mcp",
      "args": [
        "--repo",    "/absolute/path/to/repo",
        "--db",      "/absolute/path/to/codekg.sqlite",
        "--lancedb", "/absolute/path/to/lancedb"
      ]
    }
  }
}
```

Use **absolute paths** — Claude Desktop does not inherit the shell's working directory.

### Configuring Claude Code (`.mcp.json`)

For Claude Code, use `poetry run` so the entry point resolves correctly:

```json
{
  "mcpServers": {
    "codekg": {
      "command": "poetry",
      "args": [
        "run", "codekg-mcp",
        "--repo",    "/path/to/repo",
        "--db",      "/path/to/codekg.sqlite",
        "--lancedb", "/path/to/lancedb"
      ]
    }
  }
}
```

### Transport Modes

| Mode | Use case |
|---|---|
| `stdio` (default) | Claude Desktop and local agent frameworks; protocol runs over stdin/stdout |
| `sse` | HTTP-based clients; server listens on a port and streams events |

### MCP Server Properties

- **Read-only** — the server never modifies the graph
- **Stateful** — one `CodeKG` instance per server process, shared across all tool calls
- **Lazy** — the embedder and LanceDB connection are only created on first use

See `docs/MCP.md` for the full MCP reference including query strategy guide, tool schemas, and troubleshooting.

---

## `/setup-mcp` Claude Skill

The repository ships a **Claude skill** at `.claude/commands/setup-mcp.md` that automates the full MCP setup workflow. Invoke it from Claude Code:

```
/setup-mcp [/path/to/repo]
```

The skill executes these steps in sequence:

1. **Resolve the target repository** — verifies the path contains Python files
2. **Verify CodeKG installation** — checks `codekg-mcp` is available; installs the `mcp` extra if needed
3. **Build the SQLite graph** — runs `codekg-build-sqlite`, reports node/edge counts
4. **Build the LanceDB index** — runs `codekg-build-lancedb`, reports vector count
5. **Smoke-test the pipeline** — runs `kg.stats()` and a sample query end-to-end
6. **Configure MCP clients** — writes/updates both `.mcp.json` (Claude Code) and `claude_desktop_config.json` (Claude Desktop) with correct absolute paths
7. **Final report** — summarises all steps and reminds the user to restart their agent

---

## CLI Entry Points

All six entry points are registered in `pyproject.toml`:

| Command | Module | Description |
|---|---|---|
| `codekg-build-sqlite` | `build_codekg_sqlite` | repo → SQLite |
| `codekg-build-lancedb` | `build_codekg_lancedb` | SQLite → LanceDB |
| `codekg-query` | `codekg_query` | hybrid query, text output |
| `codekg-pack` | `codekg_snippet_packer` | hybrid query + snippet pack |
| `codekg-viz` | `codekg_viz` | launch Streamlit visualizer |
| `codekg-mcp` | `mcp_server` | start MCP server |

Each CLI module is a thin wrapper that constructs the appropriate class(es) and delegates.

---

## Source Layout

```
code_kg/
├── src/code_kg/
│   ├── codekg.py                # Locked v0 primitives: Node, Edge, extract_repo
│   ├── graph.py                 # CodeGraph — pure AST extraction
│   ├── store.py                 # GraphStore — SQLite persistence + traversal
│   ├── index.py                 # SemanticIndex, Embedder, SeedHit
│   ├── kg.py                    # CodeKG orchestrator + BuildStats, QueryResult, SnippetPack
│   ├── build_codekg_sqlite.py   # CLI: repo → SQLite
│   ├── build_codekg_lancedb.py  # CLI: SQLite → LanceDB
│   ├── codekg_query.py          # CLI: hybrid query
│   ├── codekg_snippet_packer.py # CLI: snippet pack
│   ├── codekg_viz.py            # CLI: launch Streamlit visualizer
│   └── mcp_server.py            # MCP server (FastMCP, optional dep)
├── app.py                       # Streamlit web application
├── Dockerfile                   # Docker image definition
├── docker-compose.yml           # Docker Compose service
├── .streamlit/config.toml       # Streamlit server config
├── .mcp.json                    # Claude Code MCP configuration
├── .claude/commands/setup-mcp.md # /setup-mcp Claude skill
├── tests/
│   ├── test_primitives.py       # Node, Edge, extract_repo, helpers (40 tests)
│   ├── test_graph.py            # CodeGraph (12 tests)
│   ├── test_store.py            # GraphStore (18 tests)
│   └── test_kg.py               # CodeKG, result types, span utilities (28 tests)
└── docs/
    ├── Architecture.md          # This document
    ├── MCP.md                   # MCP server reference
    └── docker.md                # Docker setup reference
```

---

## Data Flow Summary

```
Repository (.py files)
        │
        ▼  CodeGraph.extract()
  (nodes, edges)          ← pure, deterministic, no I/O
        │
        ▼  GraphStore.write()
  codekg.sqlite           ← authoritative, canonical
  ┌─────────────┐
  │ nodes table │
  │ edges table │
  └─────────────┘
        │
        ▼  SemanticIndex.build()
  lancedb_dir/            ← derived, disposable
  ┌──────────────────┐
  │ codekg_nodes tbl │
  │ (id, vector, …)  │
  └──────────────────┘
        │
        ▼  CodeKG.query() / .pack()
  semantic seeds (LanceDB)
        +
  structural expansion (SQLite)
        │
        ▼  rank + dedupe
  QueryResult / SnippetPack
        │
        ▼
  Markdown / JSON output
        │
        ├──▶  Streamlit app (app.py)     ← interactive browser
        └──▶  MCP server (mcp_server.py) ← AI agent tools
```

---

## Dependencies

| Package | Role |
|---|---|
| `lancedb ≥ 0.6.0` | Vector database for semantic index |
| `sentence-transformers ≥ 2.7.0` | Local embedding model |
| `numpy ≥ 1.24.0` | Vector arithmetic |
| `streamlit ≥ 1.35.0` | Web application framework |
| `pyvis ≥ 0.3.2` | Interactive graph visualization |
| `pandas ≥ 2.0.0` | Tabular data display in Streamlit |
| `mcp ≥ 1.0.0` *(optional)* | Model Context Protocol server |
| Python `ast` (stdlib) | AST parsing — no external dep |
| Python `sqlite3` (stdlib) | Relational graph store |

Python ≥ 3.10, < 3.13.

Install the MCP extra with:
```bash
pip install "code-kg[mcp]"
```
