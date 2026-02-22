## CodeKG v0.2.0

> **Major refactor: layered architecture, zero-config CLI, MCP token efficiency**

This release completes the architectural rewrite begun after v0.1.0, promotes the package to **Beta**, and ships several quality-of-life improvements for AI agents consuming the MCP tools.

---

### Highlights

#### Layered Architecture

The monolithic extraction code has been split into three composable layers with a clean orchestrator on top:

| Module | Class | Role |
|--------|-------|------|
| `graph.py` | `CodeGraph` | Pure AST extraction, no side effects |
| `store.py` | `GraphStore` | SQLite persistence + graph traversal |
| `index.py` | `SemanticIndex` | LanceDB semantic search + `Embedder` ABC |
| `kg.py` | `CodeKG` | Orchestrator: build, query, pack |

All result types (`BuildStats`, `QueryResult`, `Snippet`, `SnippetPack`) are importable directly from `code_kg`.

#### `python -m code_kg` — Zero-Dependency Invocation

A new `__main__.py` dispatcher makes every subcommand available without an activated venv or `poetry run`:

```bash
python -m code_kg build-sqlite
python -m code_kg build-lancedb
python -m code_kg query --q "database connection"
python -m code_kg mcp
```

All CLI entry points now have zero-config defaults — run from a repo root and `.codekg/graph.sqlite` / `.codekg/lancedb` are used automatically.

#### MCP Token Efficiency

Two changes reduce context-window pressure for AI agents:

- **`query_codebase`** — new `max_nodes` parameter (default **25**) caps the node list so large graphs don't flood the context.
- **`pack_snippets`** — defaults tightened: `max_lines` **160 → 60**, `max_nodes` **50 → 15**. Snippet packs are now concise by default; pass larger values explicitly when needed.

#### Install Script Overhaul

`scripts/install-skill.sh` no longer requires Poetry or an activated venv:

- Detects the right Python interpreter automatically (`.venv/bin/python` → `python3` on PATH → `pip install`)
- Writes MCP configs with the absolute Python path and `-m code_kg mcp` args
- New flags: `--providers` (selectively configure `claude`, `kilo`, `copilot`, `cline`), `--dry-run`, `--wipe`

#### `.codekg/` Unified Artifact Directory

All generated artifacts now live under `.codekg/`:

```
.codekg/
├── graph.sqlite     # knowledge graph
└── lancedb/         # vector index
```

Updated across all CLI tools, the MCP server, `.mcp.json`, `.vscode/mcp.json`, and all documentation.

---

### MCP Tools

| Tool | Description |
|------|-------------|
| `graph_stats` | Node/edge counts broken down by kind |
| `query_codebase` | Hybrid semantic + graph traversal; supports `max_nodes` cap |
| `pack_snippets` | Source-grounded snippet extraction with tighter defaults |
| `get_node` | Fetch a single node by stable ID |

---

### Installation

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/suchanek/code_kg/main/scripts/install-skill.sh)
```

Or to reinstall / update an existing deployment:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/suchanek/code_kg/main/scripts/install-skill.sh) --wipe
```

See the [README](README.md) for full usage and configuration details.
