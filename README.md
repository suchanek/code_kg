
[![Python](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12-blue.svg)](https://www.python.org/)
[![License: PolyForm NC](https://img.shields.io/badge/License-PolyForm%20NC%201.0-blue.svg)](https://polyformproject.org/licenses/noncommercial/1.0.0)
[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/suchanek/code_kg/releases)
[![CI](https://github.com/suchanek/code_kg/actions/workflows/ci.yml/badge.svg)](https://github.com/suchanek/code_kg/actions/workflows/ci.yml)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)

<p align="center">
  <img src="docs/logo.png" alt="CodeKG logo" width="320"/>
</p>

**CodeKG** — A Deterministic Knowledge Graph for Python Codebases
with Semantic Indexing and Source-Grounded Snippet Packing

*Author: Eric G. Suchanek, PhD*

---

## Overview

CodeKG constructs a **deterministic, explainable knowledge graph** from a Python codebase using static analysis. The graph captures structural relationships — definitions, calls, imports, and inheritance — directly from the Python AST, stores them in SQLite, and augments retrieval with vector embeddings via LanceDB.

Structure is treated as **ground truth**; semantic search is strictly an acceleration layer. The result is a searchable, auditable representation of a codebase that supports precise navigation, contextual snippet extraction, and downstream reasoning without hallucination — making it an ideal retrieval engine for LLMs and a practical foundation for **Knowledge-Graph RAG (KRAG)**, in contrast to embedding-only approaches such as Amplify and probabilistic graph methods such as Microsoft GraphRAG.

The system ships with a Python library, CLI tools, an interactive Streamlit web app, and an MCP server for AI agent integration.

---

## Motivation

As Python systems grow, basic architectural questions become difficult:

- Where is configuration actually defined?
- Which functions participate in connection setup and verification?
- How does behavior propagate through runtime logic?
- Where are specific services or APIs invoked, and in what context?

Text search and IDE symbol lookup are brittle. LLMs provide semantic intuition but are not source-grounded. CodeKG bridges this gap by constructing a first-principles representation of code structure and layering semantic retrieval on top — without surrendering determinism or provenance.

---

## Design Principles

1. **Structure is authoritative** — The AST-derived graph is the source of truth.
2. **Semantics accelerate, never decide** — Vector embeddings seed and rank retrieval but never invent structure.
3. **Everything is traceable** — Nodes and edges map to concrete files and line numbers.
4. **Determinism over heuristics** — Identical input yields identical output.
5. **Composable artifacts** — SQLite for structure, LanceDB for vectors, Markdown/JSON for consumption.

---

## Core Data Model

### Nodes

Nodes represent concrete program elements extracted from the source tree:

| Kind       | Description                         |
|------------|-------------------------------------|
| `module`   | Python source file                  |
| `class`    | Class definition                    |
| `function` | Top-level function                  |
| `method`   | Class method                        |
| `symbol`   | Names, attributes, call expressions |

Each node stores a stable deterministic `id`, `kind`, `name`, `qualname`, `module_path`, `lineno`, `end_lineno`, and optional `docstring`. Nodes live in **SQLite**, which is canonical.

### Edges

Edges encode semantic relationships between nodes:

| Relation   | Meaning                           |
|------------|-----------------------------------|
| `CONTAINS` | Module → class/function           |
| `CALLS`    | Function/method → function/method |
| `IMPORTS`  | Module → module/symbol            |
| `INHERITS` | Class → base class                |

Edges may carry **evidence** (e.g., source line number and expression text), enabling call-site extraction and precise auditability:

```json
{
  "lineno": 586,
  "expr": "psql_path = _get_psql_path()"
}
```

---

## Build Pipeline

### Phase 1 — Static Analysis (AST → SQLite)

The repository is parsed using Python's `ast` module. All `.py` files are traversed and definitions, calls, imports, and inheritance relationships are extracted. Normalized node IDs are generated and explicit edges are emitted with associated evidence.

**Output:** a single SQLite database (`.codekg/graph.sqlite`) with `nodes` and `edges` tables.

> This phase uses **no embeddings and no LLMs**.

### Phase 2 — Semantic Indexing (SQLite → LanceDB)

To support semantic retrieval, a subset of nodes (`module`, `class`, `function`, `method`) is selected for vector indexing. Embedding text is constructed from names and docstrings, embedded using `sentence-transformers/all-MiniLM-L6-v2`, and stored in **LanceDB**.

The vector index is **derived and disposable**; SQLite remains authoritative.

---

## Hybrid Query Model

Queries execute in two explicit phases:

1. **Semantic seeding** — A natural-language query is embedded and used to retrieve a small set of semantically similar nodes from the vector index. These nodes act as conceptual entry points.

2. **Structural expansion** — From the semantic seeds, the relational graph is expanded using selected edge types (`CONTAINS`, `CALLS`, `IMPORTS`, `INHERITS`). Expansion is bounded by hop count and records provenance (minimum hop distance and originating seed).

---

## Ranking and Deduplication

Retrieved nodes are ranked deterministically by:

1. Hop distance from seed
2. Seed embedding distance
3. Node kind priority: `function`/`method` > `class` > `module` > `symbol`

To prevent redundancy, nodes are deduplicated by file and source span. Overlapping spans within the same file are merged, and a per-file cap prevents large modules from dominating results.

---

## Snippet Packing

For retained nodes, CodeKG extracts **source-grounded definition snippets** using recorded `module_path`, `lineno`, and `end_lineno`. Bounded context windows are applied to ensure readability while preserving precision. These snippet packs are suitable for:

- Human review
- LLM ingestion (grounded, not hallucinated)
- Agent pipelines

---

## Call-Site Extraction

Beyond definitions, CodeKG extracts **call-site snippets** using evidence stored on `CALLS` edges. Small source windows around invocation sites are collected, deduplicated, and ranked. This enables precise answers to questions such as *where is this function used, and under what conditions?*

---

## End-to-End Workflow

```
Repository
  ↓
AST parsing  (codekg.py)
  ↓
SQLite graph — nodes + edges  (build_codekg_sqlite.py)
  ↓
Vector indexing — LanceDB  (build_codekg_lancedb.py)
  ↓
Hybrid query — semantic + graph  (codekg_query.py)
  ↓
Ranking + deduplication
  ↓
Snippet pack — Markdown / JSON  (codekg_snippet_packer.py)
  ↓
  ├──▶  Streamlit web app  (app.py / codekg-viz)
  └──▶  MCP server tools   (codekg-mcp)
```

---

## Installation

Clone the repository and install with [Poetry](https://python-poetry.org/):

```bash
git clone https://github.com/suchanek/code_kg.git
cd code_kg
poetry install
```

To include the MCP server:

```bash
poetry install --extras mcp
```

**Requirements:** Python ≥ 3.10, < 3.13

---

## Quick Start

The fastest way to integrate CodeKG into any Python repository — run the one-line installer from within the repo you want to index:

```bash
curl -fsSL https://raw.githubusercontent.com/suchanek/code_kg/main/scripts/install-skill.sh | bash
```

The installer sets up the full **AI integration layer** end-to-end:

1. Installs `SKILL.md` reference files for Claude Code, Kilo Code, and other agents
2. Installs the `/codekg` slash command for Cline
3. Installs `codekg-mcp` if not present — prefers the latest GitHub release wheel (`pip install`), falls back to git source
4. Builds the SQLite knowledge graph (`.codekg/graph.sqlite`) and LanceDB semantic index
5. Writes MCP configuration for each provider:
   - `.mcp.json` — Claude Code and Kilo Code
   - `.vscode/mcp.json` — GitHub Copilot

By default all providers are configured. Pass `--providers` to target specific ones, or `--dry-run` to preview what the script would do without making any changes:

```bash
# All providers (default)
curl -fsSL .../install-skill.sh | bash -s -- --providers all

# Claude Code and GitHub Copilot only
curl -fsSL .../install-skill.sh | bash -s -- --providers claude,copilot

# Preview without making changes
curl -fsSL .../install-skill.sh | bash -s -- --dry-run

# Available provider names: claude, kilo, copilot, cline
```

After the script completes, reload VS Code (`Cmd+Shift+P` → `Developer: Reload Window`) to activate the MCP server. GitHub Copilot will prompt you to **Trust** the server on first use.

---

## CLI Usage

CodeKG exposes six command-line entry points:

### 1. Build the SQLite knowledge graph

```bash
codekg-build-sqlite --repo /path/to/repo --db .codekg/graph.sqlite [--wipe]
```

### 2. Build the LanceDB semantic index

```bash
codekg-build-lancedb --sqlite .codekg/graph.sqlite --lancedb .codekg/lancedb [--model all-MiniLM-L6-v2] [--wipe]
```

### 3. Run a hybrid query

```bash
codekg-query \
  --sqlite .codekg/graph.sqlite \
  --lancedb .codekg/lancedb \
  --q "database connection setup" \
  --k 8 \
  --hop 1
```

### 4. Generate a snippet pack

```bash
codekg-pack \
  --repo-root /path/to/repo \
  --sqlite .codekg/graph.sqlite \
  --lancedb .codekg/lancedb \
  --q "configuration loading" \
  --k 8 \
  --hop 1 \
  --format md \
  --out context_pack.md
```

**Key options for `codekg-pack`:**

| Option             | Default                          | Description                              |
|--------------------|----------------------------------|------------------------------------------|
| `--k`              | `8`                              | Top-K semantic hits                      |
| `--hop`            | `1`                              | Graph expansion hops                     |
| `--rels`           | `CONTAINS,CALLS,IMPORTS,INHERITS`| Edge types to expand                     |
| `--context`        | `5`                              | Extra context lines around each span     |
| `--max-lines`      | `160`                            | Max lines per snippet block              |
| `--max-nodes`      | `50`                             | Max nodes returned in pack               |
| `--format`         | `md`                             | Output format: `md` or `json`            |
| `--include-symbols`| off                              | Include symbol nodes in output           |

### 5. Launch the Streamlit visualizer

```bash
codekg-viz [--db .codekg/graph.sqlite] [--port 8501]
```

### 6. Start the MCP server

```bash
codekg-mcp \
  --repo    /path/to/repo \
  --db      /path/to/repo/.codekg/graph.sqlite \
  --lancedb /path/to/repo/.codekg/lancedb
```

---

## Streamlit Web Application

CodeKG ships an interactive knowledge-graph explorer built with Streamlit and pyvis.

```bash
codekg-viz
```

The app provides three tabs:

| Tab | Description |
|---|---|
| **🗺️ Graph Browser** | Interactive pyvis graph; filter by node kind or module path; click nodes for rich detail panels with docstrings and edges |
| **🔍 Hybrid Query** | Natural-language query → ranked nodes with graph, table, edge, and JSON views; download results |
| **📦 Snippet Pack** | Query → source-grounded code snippets; download as Markdown or JSON |

The sidebar provides one-click **Build Graph**, **Build Index**, and **Build All** buttons so you can index a new codebase without leaving the browser.

---

## Docker _(work in progress)_

A Docker image that packages the Streamlit app with all dependencies is included, but multi-repository support — cleanly switching which codebase is indexed without restarting the container — is still being worked out. This section will be expanded once that workflow is stable.

---

## MCP Server

CodeKG ships a built-in **Model Context Protocol (MCP) server** that exposes the full query pipeline as structured tools for any MCP-compatible AI agent — Claude Code, Kilo Code, GitHub Copilot, Claude Desktop, Cursor, Continue, or any custom agent.

### Prerequisites

Build the knowledge graph first (the MCP server is read-only):

```bash
codekg-build-sqlite  --repo /path/to/repo --db .codekg/graph.sqlite
codekg-build-lancedb --sqlite .codekg/graph.sqlite --lancedb .codekg/lancedb
```

> **Note:** `codekg-build-lancedb` uses `--sqlite`, not `--db`.

Install the optional `mcp` dependency:

```bash
poetry install --extras mcp
```

### Available Tools

| Tool | Description |
|---|---|
| `query_codebase(q, ...)` | Hybrid semantic + structural query; returns ranked nodes and edges as JSON |
| `pack_snippets(q, ...)` | Hybrid query + source-grounded snippet extraction; returns Markdown |
| `get_node(node_id)` | Fetch a single node by its stable ID |
| `graph_stats()` | Node and edge counts by kind/relation |

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
        "--db",      "/absolute/path/to/repo/.codekg/graph.sqlite",
        "--lancedb", "/absolute/path/to/repo/.codekg/lancedb"
      ]
    }
  }
}
```

Use **absolute paths** — Claude Desktop does not inherit your shell's working directory. Restart Claude Desktop after editing the config.

### Configuring Claude Code / Kilo Code (`.mcp.json`)

Both Claude Code and Kilo Code read per-repo config from `.mcp.json`. Point `command` directly at the `codekg-mcp` binary inside the Poetry virtual environment:

```json
{
  "mcpServers": {
    "codekg": {
      "command": "/absolute/path/to/.venv/bin/codekg-mcp",
      "args": [
        "--repo",    "/absolute/path/to/repo",
        "--db",      "/absolute/path/to/repo/.codekg/graph.sqlite",
        "--lancedb", "/absolute/path/to/repo/.codekg/lancedb"
      ]
    }
  }
}
```

> ⚠️ Use per-repo `.mcp.json` only — do NOT add `codekg` to any global settings file.

### Configuring GitHub Copilot (`.vscode/mcp.json`)

GitHub Copilot uses `.vscode/mcp.json` with a different schema (`"servers"` key, `"type": "stdio"` required). Each flag and value must be a separate element in `args`:

```json
{
  "servers": {
    "codekg": {
      "type": "stdio",
      "command": "/absolute/path/to/.venv/bin/codekg-mcp",
      "args": [
        "--repo",
        "/absolute/path/to/repo",
        "--db",
        "/absolute/path/to/repo/.codekg/graph.sqlite",
        "--lancedb",
        "/absolute/path/to/repo/.codekg/lancedb"
      ]
    }
  }
}
```

VS Code will prompt you to **Trust** the server on first use.

### Automated Setup with `/setup-mcp`

The repository ships a **Claude skill** that automates the entire MCP setup workflow. From Claude Code, run:

```
/setup-mcp [/path/to/repo]
```

The skill will:
1. Verify CodeKG installation and install the `mcp` extra if needed
2. Build the SQLite graph and LanceDB index
3. Smoke-test the full pipeline
4. Write/update both `.mcp.json` (Claude Code) and `claude_desktop_config.json` (Claude Desktop)
5. Report a summary with node/edge/vector counts

See [`docs/MCP.md`](docs/MCP.md) for the full MCP reference including tool schemas, query strategy guide, and troubleshooting.

---

## Output Artifacts

| Artifact             | Description                                      |
|----------------------|--------------------------------------------------|
| `.codekg/graph.sqlite` | Canonical knowledge graph (nodes + edges)      |
| `.codekg/lancedb/`    | Derived semantic vector index                  |
| Markdown        | Human-readable context packs with line numbers |
| JSON            | Structured payload for agent/LLM ingestion     |

---

## Project Structure

```
code_kg/
├── src/code_kg/
│   ├── codekg.py                # Core primitives: Node, Edge, extract_repo
│   ├── graph.py                 # CodeGraph — pure AST extraction
│   ├── store.py                 # GraphStore — SQLite persistence + traversal
│   ├── index.py                 # SemanticIndex, Embedder, SeedHit
│   ├── kg.py                    # CodeKG orchestrator + result types
│   ├── build_codekg_sqlite.py   # CLI: repo → SQLite
│   ├── build_codekg_lancedb.py  # CLI: SQLite → LanceDB
│   ├── codekg_query.py          # CLI: hybrid query
│   ├── codekg_snippet_packer.py # CLI: snippet pack
│   ├── codekg_viz.py            # CLI: launch Streamlit visualizer
│   ├── app.py                   # Streamlit web application
│   └── mcp_server.py            # MCP server (FastMCP, optional dep)
├── Dockerfile                   # Docker image definition
├── docker-compose.yml           # Docker Compose service
├── .streamlit/config.toml       # Streamlit server config
├── .mcp.json                    # Claude Code MCP configuration
├── .claude/commands/setup-mcp.md # /setup-mcp Claude skill
├── tests/
│   ├── test_primitives.py       # Node, Edge, extract_repo (40 tests)
│   ├── test_graph.py            # CodeGraph (12 tests)
│   ├── test_store.py            # GraphStore (18 tests)
│   └── test_kg.py               # CodeKG, result types (28 tests)
└── docs/
    ├── Architecture.md          # System architecture
    ├── MCP.md                   # MCP server reference
    └── docker.md                # Docker setup reference
```

---

## License

[PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0) — see [LICENSE](LICENSE).

Free for personal use, research, education, and noncommercial organizations. Commercial use requires a separate license.
