# CodeKG MCP Server

**Using CodeKG as a Model Context Protocol Tool Provider**

*Author: Eric G. Suchanek, PhD*

---

## Overview

CodeKG ships a built-in MCP server (`codekg-mcp`) that exposes the full hybrid query and snippet-pack pipeline as structured tools consumable by any MCP-compatible AI agent — Claude Desktop, Cursor, Continue, or any custom agent that speaks the Model Context Protocol.

The server is a thin wrapper around `CodeKG` (the orchestrator in `kg.py`). It initialises a single `CodeKG` instance at startup and routes tool calls to it. All the heavy lifting — vector search, graph traversal, snippet extraction — happens inside the existing library; the MCP layer adds no logic of its own.

---

## Prerequisites

### 1. Build the knowledge graph

The MCP server is **read-only**. The SQLite graph and LanceDB vector index must be built before starting the server.

```bash
# Step 1 — static analysis: repo → SQLite
codekg-build-sqlite --repo /path/to/repo --db codekg.sqlite

# Step 2 — semantic indexing: SQLite → LanceDB
codekg-build-lancedb --db codekg.sqlite --lancedb ./lancedb
```

Both steps are idempotent. Re-run them whenever the codebase changes.

### 2. Install the `mcp` extra

`mcp` is an optional dependency. Install it alongside the package:

```bash
# Poetry
poetry add mcp
# or install the extra
pip install "code-kg[mcp]"
```

If the `mcp` package is absent, the server exits immediately with a clear error message.

---

## Starting the Server

```bash
codekg-mcp \
  --repo    /path/to/repo \
  --db      /path/to/codekg.sqlite \
  --lancedb /path/to/lancedb
```

All arguments have defaults suitable for running from the repo root:

| Flag | Default | Description |
|---|---|---|
| `--repo` | `.` | Repository root (used for snippet path resolution) |
| `--db` | `codekg.sqlite` | SQLite knowledge graph |
| `--lancedb` | `./lancedb` | LanceDB vector index directory |
| `--model` | `all-MiniLM-L6-v2` | Sentence-transformer embedding model |
| `--transport` | `stdio` | `stdio` (Claude Desktop) or `sse` (HTTP clients) |

Startup diagnostics are printed to `stderr`; the MCP protocol runs on `stdout` (stdio transport) or an HTTP port (sse transport).

---

## Configuring Claude Desktop

Add a `codekg` entry to `claude_desktop_config.json` (typically at
`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

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

Use **absolute paths** — Claude Desktop does not inherit your shell's working directory. Restart Claude Desktop after editing the config. The `codekg` server will appear in the tool panel.

---

## Available Tools

The server registers four tools via `FastMCP`.

---

### `query_codebase`

Hybrid semantic + structural query. Returns ranked nodes and edges as JSON.

**When to use:** Exploring the graph — finding what classes, functions, and modules are relevant to a topic, understanding call relationships, tracing imports.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `q` | `str` | — | Natural-language query |
| `k` | `int` | `8` | Semantic seed count (top-K from vector search) |
| `hop` | `int` | `1` | Graph expansion hops from each seed |
| `rels` | `str` | `"CONTAINS,CALLS,IMPORTS,INHERITS"` | Comma-separated edge types to follow |
| `include_symbols` | `bool` | `false` | Include low-level `sym:` nodes |

**Returns:** JSON string matching the `QueryResult` schema:

```json
{
  "query": "database connection setup",
  "seeds": 8,
  "expanded_nodes": 34,
  "returned_nodes": 22,
  "hop": 1,
  "rels": ["CONTAINS", "CALLS", "IMPORTS", "INHERITS"],
  "nodes": [
    {
      "id": "fn:src/db/manager.py:DatabaseManager.connect_db",
      "kind": "function",
      "name": "connect_db",
      "qualname": "DatabaseManager.connect_db",
      "module_path": "src/db/manager.py",
      "lineno": 42,
      "end_lineno": 55,
      "docstring": "Establish a connection to the database."
    }
  ],
  "edges": [
    { "src": "cls:src/db/manager.py:DatabaseManager",
      "rel": "CONTAINS",
      "dst": "fn:src/db/manager.py:DatabaseManager.connect_db",
      "evidence": {} }
  ]
}
```

Nodes are sorted by composite rank: `(best_hop, seed_distance, kind_priority, node_id)`.

---

### `pack_snippets`

Hybrid query + source-grounded snippet extraction. Returns a Markdown context pack.

**When to use:** Any time you need to read actual source code — understanding an implementation, debugging, writing tests, reviewing logic. Prefer this over `query_codebase` when implementation details matter.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `q` | `str` | — | Natural-language query |
| `k` | `int` | `8` | Semantic seed count |
| `hop` | `int` | `1` | Graph expansion hops |
| `rels` | `str` | `"CONTAINS,CALLS,IMPORTS,INHERITS"` | Edge types to follow |
| `include_symbols` | `bool` | `false` | Include symbol nodes |
| `context` | `int` | `5` | Extra context lines around each definition |
| `max_lines` | `int` | `160` | Maximum lines per snippet block |
| `max_nodes` | `int` | `50` | Maximum nodes in the pack |

**Returns:** Markdown string. Each section is a ranked, deduplicated code snippet with file path and line numbers:

````markdown
## fn:src/db/manager.py:DatabaseManager.connect_db

**Kind:** function | **Module:** src/db/manager.py | **Lines:** 42–55

```python
  42: def connect_db(self):
  43:     """Establish a connection to the database."""
  44:     ...
```
````

Deduplication removes overlapping spans (within a 2-line gap) in the same file, so the pack never repeats the same source region. Total nodes are capped at `max_nodes`.

---

### `get_node`

Fetch a single node by its stable ID.

**When to use:** You have a node ID from a previous query result and want its full metadata.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `node_id` | `str` | Stable node ID, e.g. `fn:src/db/manager.py:DatabaseManager.connect_db` |

**Returns:** JSON object with all node fields, or `{"error": "Node not found: '...'"}`.

**Node ID format:** `<kind>:<module_path>:<qualname>`

| Prefix | Kind |
|---|---|
| `mod:` | module |
| `cls:` | class |
| `fn:` | function |
| `m:` | method |
| `sym:` | unresolved symbol |

---

### `graph_stats`

Return node and edge counts broken down by kind and relation.

**When to use:** Orientation — understand the size and shape of the graph before querying. Useful as a first call when starting a new session.

**Parameters:** None.

**Returns:**

```json
{
  "total_nodes": 412,
  "total_edges": 1087,
  "node_counts": {
    "module": 18,
    "class": 34,
    "function": 201,
    "method": 143,
    "symbol": 16
  },
  "edge_counts": {
    "CONTAINS": 378,
    "CALLS": 512,
    "IMPORTS": 147,
    "INHERITS": 50
  },
  "db_path": "codekg.sqlite"
}
```

---

## Query Strategy Guide

### Choosing `k` and `hop`

| Goal | Recommended settings |
|---|---|
| Narrow, precise lookup | `k=4, hop=0` — seeds only, no expansion |
| Standard exploration | `k=8, hop=1` — default; good for most queries |
| Broad context sweep | `k=12, hop=2` — pulls in more of the call graph |
| Deep dependency trace | `k=8, hop=2, rels="CALLS,IMPORTS"` — follow execution paths |

Higher `hop` values expand the result set geometrically. `hop=2` on a large codebase can return hundreds of nodes; use `max_nodes` in `pack_snippets` to keep the output manageable.

### Choosing `rels`

| Relation | Meaning | When to include |
|---|---|---|
| `CONTAINS` | Module/class contains a definition | Almost always — provides structural context |
| `CALLS` | Function A calls function B | Tracing execution flow, finding callers/callees |
| `IMPORTS` | Module A imports from module B | Dependency analysis |
| `INHERITS` | Class A inherits from class B | OOP hierarchy exploration |

Default (`CONTAINS,CALLS,IMPORTS,INHERITS`) is appropriate for most queries. Restrict to `CALLS` alone for pure call-graph traversal.

### `include_symbols`

`sym:` nodes represent unresolved call targets — external library calls or dynamically constructed names that the AST pass could not resolve to a definition in the repo. They are excluded by default. Include them only when you specifically want to see what external symbols a function calls.

---

## How It Works (End-to-End)

When an agent calls `pack_snippets("database connection setup")`:

```
1. query string
        │
        ▼  SemanticIndex.search(k=8)
   top-8 SeedHit list          ← vector similarity in LanceDB
        │
        ▼  GraphStore.expand(hop=1, rels=…)
   Dict[node_id, ProvMeta]     ← BFS over SQLite edges
        │
        ▼  rank + deduplicate
   ordered node list            ← (best_hop, distance, kind_priority, id)
        │
        ▼  snippet extraction
   source lines from disk       ← path-traversal-safe file reads
        │
        ▼  SnippetPack.to_markdown()
   Markdown string              ← returned to agent
```

The SQLite graph is the authoritative source of truth. The LanceDB index is derived and disposable — it can be rebuilt at any time with `codekg-build-lancedb` without touching the graph.

---

## Typical Agent Workflow

A well-behaved agent session might look like this:

```
1. graph_stats()
   → understand the codebase size and shape

2. query_codebase("authentication flow", k=8, hop=1)
   → identify relevant classes and functions, note their IDs

3. pack_snippets("JWT token validation", k=6, hop=1)
   → read the actual implementation

4. get_node("fn:src/auth/jwt.py:JWTValidator.validate")
   → fetch metadata for a specific node found in step 2

5. pack_snippets("JWT token validation error handling", k=4, hop=2, rels="CALLS")
   → follow the call graph deeper into error paths
```

---

## Transport Modes

### `stdio` (default)

Used by Claude Desktop and most local agent frameworks. The MCP protocol runs over stdin/stdout. The server process is launched and managed by the host application.

```bash
codekg-mcp --repo . --db codekg.sqlite --lancedb ./lancedb --transport stdio
```

### `sse` (Server-Sent Events)

Used by HTTP-based clients. The server listens on a port and streams events over HTTP. Useful for remote deployments or multi-client setups.

```bash
codekg-mcp --repo . --db codekg.sqlite --lancedb ./lancedb --transport sse
```

---

## Programmatic Use (Python)

You can drive the same `CodeKG` instance directly from Python without the MCP layer — useful for testing queries before wiring up an agent:

```python
from code_kg import CodeKG

kg = CodeKG(
    repo_root="/path/to/repo",
    db_path="codekg.sqlite",
    lancedb_dir="./lancedb",
)

# Equivalent to query_codebase tool
result = kg.query("database connection setup", k=8, hop=1)
print(result.to_json())

# Equivalent to pack_snippets tool
pack = kg.pack("configuration loading", k=8, hop=1)
print(pack.to_markdown())

# Equivalent to get_node tool
node = kg.node("fn:src/db/manager.py:DatabaseManager.connect_db")
print(node)

# Equivalent to graph_stats tool
stats = kg.stats()
print(stats)
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ERROR: 'mcp' package not found` | Optional dep not installed | `pip install "code-kg[mcp]"` or `poetry add mcp` |
| `WARNING: SQLite database not found` | Graph not built yet | Run `codekg-build-sqlite` then `codekg-build-lancedb` |
| Empty results from `query_codebase` | LanceDB index missing or stale | Run `codekg-build-lancedb --wipe` |
| Node IDs in results don't resolve with `get_node` | Graph rebuilt since last query | Rebuild both SQLite and LanceDB |
| `RuntimeError: CodeKG not initialised` | Server called without `main()` | Always start via `codekg-mcp` CLI |
| Snippets show wrong line numbers | Source files changed since build | Rebuild with `codekg-build-sqlite --wipe` |

---

## Summary

| Concern | Answer |
|---|---|
| What does the MCP server expose? | 4 tools: `query_codebase`, `pack_snippets`, `get_node`, `graph_stats` |
| What must exist before starting? | `codekg.sqlite` + `lancedb/` directory (built by the two CLI commands) |
| Is the server stateful? | Yes — one `CodeKG` instance per server process, shared across all tool calls |
| Can it modify the graph? | No — the MCP server is strictly read-only |
| What transport should I use? | `stdio` for Claude Desktop / local agents; `sse` for HTTP clients |
| Which tool should I call first? | `graph_stats` for orientation, then `pack_snippets` for implementation details |
