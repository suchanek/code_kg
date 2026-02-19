# CodeKG MCP Installation Guide

**Integrating CodeKG with Claude Code and Claude Desktop**

*Author: Eric G. Suchanek, PhD*

---

## Overview

CodeKG ships a built-in MCP server (`codekg-mcp`) that exposes the full hybrid query and snippet-pack pipeline as structured tools consumable by any MCP-compatible AI agent — Claude Code, Claude Desktop, Cursor, Continue, or any custom agent that speaks the Model Context Protocol.

Once configured, the agent gains four tools:

| Tool | Purpose |
|---|---|
| `graph_stats()` | Codebase size and shape — good first call |
| `query_codebase(q)` | Semantic + structural graph exploration |
| `pack_snippets(q)` | Source-grounded code snippets for implementation detail |
| `get_node(node_id)` | Single node metadata lookup by stable ID |

---

## Quick Start (TL;DR)

```bash
# 1. Install code-kg with the MCP extra into your project
poetry add "code-kg[mcp] @ git+https://github.com/suchanek/code_kg.git"

# 2. Build the knowledge graph
poetry run codekg-build-sqlite  --repo . --db codekg.sqlite
poetry run codekg-build-lancedb --sqlite codekg.sqlite --lancedb ./lancedb

# 3. Add .mcp.json to your project root (see Section 4)

# 4. Restart Claude Code — the codekg tools are now active
```

Or use the automated setup command inside Claude Code:

```
/setup-mcp
```

---

## Bootstrap: New Machine Setup

On a **brand-new machine** the Claude skill doesn't exist yet, so Claude won't know how to help you set up CodeKG. Install the skill first with a single command — no clone required:

```bash
curl -fsSL https://raw.githubusercontent.com/suchanek/code_kg/main/scripts/install-skill.sh | bash
```

Or, if you already have the repo cloned:

```bash
bash scripts/install-skill.sh
```

This installs `~/.claude/skills/codekg/` so that any Claude Code session (with `skills-copilot` running) will automatically have expert CodeKG knowledge available. Then proceed with the normal installation steps below.

---

## Table of Contents

1. [Installation](#1-installation)
2. [Building the Knowledge Graph](#2-building-the-knowledge-graph)
3. [Smoke-Testing the Pipeline](#3-smoke-testing-the-pipeline)
4. [Configuring Claude Code](#4-configuring-claude-code)
5. [Configuring Claude Desktop](#5-configuring-claude-desktop)
6. [Automated Setup with `/setup-mcp`](#6-automated-setup-with-setup-mcp)
7. [Claude Copilot Integration](#7-claude-copilot-integration)
8. [Available Tools Reference](#8-available-tools-reference)
9. [Query Strategy Guide](#9-query-strategy-guide)
10. [Rebuilding After Code Changes](#10-rebuilding-after-code-changes)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Installation

### 1a. Install from GitHub (recommended until PyPI release)

In the target project's directory:

```bash
# Basic install (no MCP server)
poetry add git+https://github.com/suchanek/code_kg.git

# With MCP server support (required for codekg-mcp)
poetry add "code-kg[mcp] @ git+https://github.com/suchanek/code_kg.git"
```

This adds the following to your `pyproject.toml`:

```toml
[tool.poetry.dependencies]
code-kg = { git = "https://github.com/suchanek/code_kg.git", extras = ["mcp"] }
```

Then run:

```bash
poetry lock && poetry install
```

### 1b. Pin to a specific commit

```toml
code-kg = { git = "https://github.com/suchanek/code_kg.git", rev = "66d565f", extras = ["mcp"] }
```

### 1c. Verify the install

```bash
# Confirm entry points are available
poetry run which codekg-mcp
poetry run which codekg-build-sqlite
poetry run which codekg-build-lancedb

# Confirm the mcp package is importable
poetry run python -c "import mcp; print('mcp OK')"
```

If `codekg-mcp` is missing but the package is installed, the `mcp` extra is absent — add it:

```bash
poetry add mcp
```

---

## 2. Building the Knowledge Graph

The MCP server is **read-only**. Two artifacts must be built before starting the server:

| Artifact | Built by | Contains |
|---|---|---|
| `codekg.sqlite` | `codekg-build-sqlite` | AST-extracted nodes and edges |
| `lancedb/` | `codekg-build-lancedb` | Sentence-transformer vector embeddings |

### Step 1 — Static analysis: repo → SQLite

```bash
poetry run codekg-build-sqlite \
  --repo /absolute/path/to/repo \
  --db   /absolute/path/to/repo/codekg.sqlite
```

Add `--wipe` to rebuild from scratch (safe to re-run):

```bash
poetry run codekg-build-sqlite --repo . --db codekg.sqlite --wipe
```

**Output:** `OK: nodes=<N> edges=<M> db=codekg.sqlite`

### Step 2 — Semantic indexing: SQLite → LanceDB

> **Note:** The flag is `--sqlite`, not `--db`.

```bash
poetry run codekg-build-lancedb \
  --sqlite /absolute/path/to/repo/codekg.sqlite \
  --lancedb /absolute/path/to/repo/lancedb
```

Add `--wipe` to rebuild the vector index:

```bash
poetry run codekg-build-lancedb --sqlite codekg.sqlite --lancedb ./lancedb --wipe
```

**Output:** `OK: indexed_rows=<V> dim=384 table=codekg_nodes lancedb_dir=./lancedb kinds=module,class,function,method`

Both steps are idempotent. Re-run them whenever the codebase changes significantly.

### CLI flags reference

**`codekg-build-sqlite`**

| Flag | Required | Default | Description |
|---|---|---|---|
| `--repo` | ✓ | — | Repository root path |
| `--db` | ✓ | — | SQLite output path |
| `--wipe` | | false | Delete existing graph first |

**`codekg-build-lancedb`**

| Flag | Required | Default | Description |
|---|---|---|---|
| `--sqlite` | ✓ | — | Path to `codekg.sqlite` |
| `--lancedb` | ✓ | — | LanceDB output directory |
| `--table` | | `codekg_nodes` | LanceDB table name |
| `--model` | | `all-MiniLM-L6-v2` | Sentence-transformer model |
| `--wipe` | | false | Delete existing vectors first |
| `--kinds` | | `module,class,function,method` | Node kinds to embed |
| `--batch` | | `256` | Embedding batch size |

---

## 3. Smoke-Testing the Pipeline

Before configuring any agent, verify the full pipeline works end-to-end:

```bash
# Check graph stats
poetry run python -c "
from code_kg import CodeKG
import json
kg = CodeKG(repo_root='.', db_path='codekg.sqlite', lancedb_dir='./lancedb')
print(json.dumps(kg.stats(), indent=2))
"

# Run a sample query
poetry run codekg-query \
  --sqlite codekg.sqlite \
  --lancedb ./lancedb \
  --q "module structure"
```

Expected output from `kg.stats()`:

```json
{
  "total_nodes": 412,
  "total_edges": 1087,
  "node_counts": { "module": 18, "class": 34, "function": 201, "method": 143 },
  "edge_counts": { "CONTAINS": 378, "CALLS": 512, "IMPORTS": 147, "INHERITS": 50 },
  "db_path": "codekg.sqlite"
}
```

If this succeeds, the MCP server will work correctly.

---

## 4. Configuring Claude Code

Claude Code reads MCP server configuration from `.mcp.json` in the **project root**.

### 4a. Create or update `.mcp.json`

```json
{
  "mcpServers": {
    "codekg": {
      "command": "poetry",
      "args": [
        "run", "codekg-mcp",
        "--repo",    "/absolute/path/to/repo",
        "--db",      "/absolute/path/to/repo/codekg.sqlite",
        "--lancedb", "/absolute/path/to/repo/lancedb"
      ],
      "env": {
        "POETRY_VIRTUALENVS_IN_PROJECT": "false"
      }
    }
  }
}
```

> **Always use absolute paths.** Claude Code does not inherit your shell's working directory.

### 4b. Merging with existing `.mcp.json`

If you already have other MCP servers configured (e.g. `copilot-memory`, `skills-copilot`, `task-copilot`), add the `codekg` entry to the existing `mcpServers` object — do not overwrite other entries:

```json
{
  "mcpServers": {
    "copilot-memory": { "...": "existing entry" },
    "skills-copilot":  { "...": "existing entry" },
    "task-copilot":    { "...": "existing entry" },
    "codekg": {
      "command": "poetry",
      "args": [
        "run", "codekg-mcp",
        "--repo",    "/absolute/path/to/repo",
        "--db",      "/absolute/path/to/repo/codekg.sqlite",
        "--lancedb", "/absolute/path/to/repo/lancedb"
      ]
    }
  }
}
```

### 4c. Activate

Restart Claude Code (close and reopen the project). The `codekg` server will appear in the MCP tools panel.

---

## 5. Configuring Claude Desktop

Claude Desktop does not have Poetry on its PATH, so you must use the **absolute path to the venv binary**.

### 5a. Find the venv binary path

```bash
# In the project directory
poetry env info --path
# → /Users/you/Library/Caches/pypoetry/virtualenvs/my-project-abc123-py3.11
```

The `codekg-mcp` binary is at `<venv_path>/bin/codekg-mcp`.

### 5b. Edit `claude_desktop_config.json`

| OS | Config path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

Add the `codekg` entry:

```json
{
  "mcpServers": {
    "codekg": {
      "command": "/Users/you/Library/Caches/pypoetry/virtualenvs/my-project-abc123-py3.11/bin/codekg-mcp",
      "args": [
        "--repo",    "/absolute/path/to/repo",
        "--db",      "/absolute/path/to/repo/codekg.sqlite",
        "--lancedb", "/absolute/path/to/repo/lancedb"
      ]
    }
  }
}
```

### 5c. Activate

Restart Claude Desktop. The `codekg` server will appear in the tool panel.

---

## 6. Automated Setup with `/setup-mcp`

If your project uses **Claude Copilot**, the `/setup-mcp` command automates the entire installation and configuration process.

### Usage

```
/setup-mcp                        # Interactive — prompts for repo path
/setup-mcp /path/to/repo          # Non-interactive — uses provided path
```

### What it does

The command runs six steps automatically:

| Step | Action |
|---|---|
| 0 | Resolves the target repository path and verifies Python files exist |
| 1 | Verifies `codekg-mcp` is installed; installs `code-kg[mcp]` if missing |
| 2 | Builds the SQLite knowledge graph (asks before wiping existing data) |
| 3 | Builds the LanceDB vector index (asks before wiping existing data) |
| 4 | Smoke-tests the full query pipeline |
| 5 | Writes/updates `.mcp.json` (Claude Code) and `claude_desktop_config.json` (Claude Desktop) |
| 6 | Prints a final summary with node/edge/vector counts and next steps |

### Example output

```
✓ Repository indexed:    /path/to/repo
✓ SQLite graph:          /path/to/repo/codekg.sqlite  (412 nodes, 1087 edges)
✓ LanceDB index:         /path/to/repo/lancedb  (378 vectors)
✓ Smoke test:            passed
✓ Claude Code config:    /path/to/repo/.mcp.json
✓ Claude Desktop config: ~/Library/Application Support/Claude/claude_desktop_config.json

Restart Claude Code / Claude Desktop to activate the codekg MCP server.

Available tools once active:
  • graph_stats()          — codebase size and shape
  • query_codebase(q)      — semantic + structural exploration
  • pack_snippets(q)       — source-grounded code snippets
  • get_node(node_id)      — single node metadata lookup

Suggested first query after restart:
  graph_stats()
```

---

## 7. Claude Copilot Integration

If your project uses [Claude Copilot](https://github.com/Everyone-Needs-A-Copilot/claude-copilot), CodeKG integrates naturally with the agent framework.

### Setting up Claude Copilot in a new project

Claude Copilot provides the agent infrastructure (Memory Copilot, Task Copilot, Skills, Agents). To set it up alongside CodeKG:

```
/setup-project          # Initialize Claude Copilot
/setup-mcp              # Then set up CodeKG MCP
```

### Project structure with both installed

```
your-project/
├── .mcp.json                    ← MCP server config (codekg + copilot servers)
├── .claude/
│   ├── settings.local.json      ← Claude Code settings
│   ├── agents/                  ← Agent definitions (ta, me, qa, doc, etc.)
│   ├── commands/
│   │   ├── protocol.md          ← /protocol command
│   │   ├── continue.md          ← /continue command
│   │   └── setup-mcp.md         ← /setup-mcp command
│   └── skills/                  ← Local skills (empty until populated)
├── codekg.sqlite                ← Knowledge graph (gitignored)
└── lancedb/                     ← Vector index (gitignored)
```

### Recommended `.mcp.json` with full Copilot stack

```json
{
  "mcpServers": {
    "copilot-memory": {
      "command": "node",
      "args": ["/Users/you/.claude/copilot/mcp-servers/copilot-memory/dist/index.js"],
      "env": {
        "MEMORY_PATH": "/Users/you/.claude/memory",
        "WORKSPACE_ID": "your-project"
      }
    },
    "skills-copilot": {
      "command": "node",
      "args": ["/Users/you/.claude/copilot/mcp-servers/skills-copilot/dist/index.js"],
      "env": {
        "LOCAL_SKILLS_PATH": "./.claude/skills"
      }
    },
    "task-copilot": {
      "command": "node",
      "args": ["/Users/you/.claude/copilot/mcp-servers/task-copilot/dist/index.js"],
      "env": {
        "TASK_DB_PATH": "/Users/you/.claude/tasks",
        "WORKSPACE_ID": "your-project"
      }
    },
    "codekg": {
      "command": "poetry",
      "args": [
        "run", "codekg-mcp",
        "--repo",    "/absolute/path/to/your-project",
        "--db",      "/absolute/path/to/your-project/codekg.sqlite",
        "--lancedb", "/absolute/path/to/your-project/lancedb"
      ]
    }
  }
}
```

### Using CodeKG tools within the Agent-First Protocol

When working under `/protocol`, agents can call CodeKG tools directly. The recommended workflow:

```
1. Start session:
   /protocol

2. Agent orientation (agent calls automatically):
   graph_stats()                          → understand codebase shape

3. Investigation (agent calls):
   query_codebase("authentication flow")  → find relevant nodes
   pack_snippets("JWT validation logic")  → read implementation

4. Implementation:
   @agent-me implements changes with full source context from pack_snippets
```

The `@agent-doc` agent is particularly well-suited to use `pack_snippets` when generating documentation — it gets accurate source-grounded snippets rather than hallucinating implementations.

---

## 8. Available Tools Reference

### `graph_stats()`

Return node and edge counts broken down by kind and relation.

**When to use:** First call in any session — understand the codebase size and shape before querying.

**Parameters:** None.

**Returns:**

```json
{
  "total_nodes": 412,
  "total_edges": 1087,
  "node_counts": {
    "module": 18, "class": 34, "function": 201, "method": 143, "symbol": 16
  },
  "edge_counts": {
    "CONTAINS": 378, "CALLS": 512, "IMPORTS": 147, "INHERITS": 50
  },
  "db_path": "codekg.sqlite"
}
```

---

### `query_codebase(q, k, hop, rels, include_symbols)`

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

**Returns:** JSON with keys: `query`, `seeds`, `expanded_nodes`, `returned_nodes`, `hop`, `rels`, `nodes`, `edges`.

---

### `pack_snippets(q, k, hop, rels, include_symbols, context, max_lines, max_nodes)`

Hybrid query + source-grounded snippet extraction. Returns a Markdown context pack.

**When to use:** Any time you need to read actual source code — understanding an implementation, debugging, writing tests, reviewing logic. **Prefer this over `query_codebase` when implementation details matter.**

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

**Returns:** Markdown string with ranked, deduplicated code snippets and line numbers.

---

### `get_node(node_id)`

Fetch a single node by its stable ID.

**When to use:** You have a node ID from a previous query result and want its full metadata.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `node_id` | `str` | Stable node ID, e.g. `fn:src/auth/jwt.py:JWTValidator.validate` |

**Node ID format:** `<kind>:<module_path>:<qualname>`

| Prefix | Kind |
|---|---|
| `mod:` | module |
| `cls:` | class |
| `fn:` | function / method |
| `sym:` | unresolved external symbol |

**Returns:** JSON object with all node fields, or `{"error": "Node not found: '...'"}`.

---

## 9. Query Strategy Guide

### Choosing `k` and `hop`

| Goal | Recommended settings |
|---|---|
| Narrow, precise lookup | `k=4, hop=0` — seeds only, no expansion |
| Standard exploration | `k=8, hop=1` — default; good for most queries |
| Broad context sweep | `k=12, hop=2` — pulls in more of the call graph |
| Deep dependency trace | `k=8, hop=2, rels="CALLS,IMPORTS"` — follow execution paths |

Higher `hop` values expand the result set geometrically. Use `max_nodes` in `pack_snippets` to keep output manageable.

### Choosing `rels`

| Relation | Meaning | When to include |
|---|---|---|
| `CONTAINS` | Module/class contains a definition | Almost always — provides structural context |
| `CALLS` | Function A calls function B | Tracing execution flow, finding callers/callees |
| `IMPORTS` | Module A imports from module B | Dependency analysis |
| `INHERITS` | Class A inherits from class B | OOP hierarchy exploration |

### Typical agent workflow

```
1. graph_stats()
   → understand codebase size and shape

2. query_codebase("authentication flow", k=8, hop=1)
   → identify relevant classes and functions, note their IDs

3. pack_snippets("JWT token validation", k=6, hop=1)
   → read the actual implementation

4. get_node("fn:src/auth/jwt.py:JWTValidator.validate")
   → fetch metadata for a specific node

5. pack_snippets("JWT token validation error handling", k=4, hop=2, rels="CALLS")
   → follow the call graph deeper into error paths
```

---

## 10. Rebuilding After Code Changes

When the codebase changes, rebuild both artifacts (safe to re-run, idempotent):

```bash
poetry run codekg-build-sqlite  --repo . --db codekg.sqlite --wipe
poetry run codekg-build-lancedb --sqlite codekg.sqlite --lancedb ./lancedb --wipe
```

The `.mcp.json` and `claude_desktop_config.json` entries do not need to change — they point to the same file paths.

### Gitignore recommendations

Add these to `.gitignore` to avoid committing large binary artifacts:

```gitignore
codekg.sqlite
codekg.sqlite-shm
codekg.sqlite-wal
lancedb/
```

---

## 11. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ERROR: 'mcp' package not found` | Optional dep not installed | `poetry add mcp` or `poetry add "code-kg[mcp]"` |
| `WARNING: SQLite database not found` | Graph not built yet | Run `codekg-build-sqlite` then `codekg-build-lancedb` |
| `codekg-build-lancedb: error: the following arguments are required: --sqlite` | Wrong flag name | Use `--sqlite`, not `--db`, for the lancedb builder |
| Empty results from `query_codebase` | LanceDB index missing or stale | Run `codekg-build-lancedb --wipe` |
| Node IDs in results don't resolve with `get_node` | Graph rebuilt since last query | Rebuild both SQLite and LanceDB |
| `RuntimeError: CodeKG not initialised` | Server called without `main()` | Always start via `codekg-mcp` CLI |
| Snippets show wrong line numbers | Source files changed since build | Rebuild with `codekg-build-sqlite --wipe` |
| MCP server not appearing in Claude Code | `.mcp.json` not in project root, or relative paths used | Use absolute paths; restart Claude Code |
| MCP server not appearing in Claude Desktop | Wrong binary path or relative paths | Use `poetry env info --path` to get absolute venv path |
| `poetry run which codekg-mcp` returns nothing | `mcp` extra not installed | `poetry add "code-kg[mcp]"` |

---

## Summary

| Concern | Answer |
|---|---|
| What does the MCP server expose? | 4 tools: `graph_stats`, `query_codebase`, `pack_snippets`, `get_node` |
| What must exist before starting? | `codekg.sqlite` + `lancedb/` directory |
| How do I build those? | `codekg-build-sqlite` then `codekg-build-lancedb --sqlite ...` |
| Is the server stateful? | Yes — one `CodeKG` instance per server process |
| Can it modify the graph? | No — strictly read-only |
| What transport should I use? | `stdio` for Claude Code / Claude Desktop; `sse` for HTTP clients |
| Which tool should I call first? | `graph_stats()` for orientation |
| How do I automate setup? | `/setup-mcp` command (requires Claude Copilot) |
