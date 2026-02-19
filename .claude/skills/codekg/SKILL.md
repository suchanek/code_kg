---
name: codekg
description: Expert knowledge for installing, configuring, and using the CodeKG MCP server — a hybrid semantic + structural knowledge graph for Python codebases. Use this skill when the user asks about: setting up CodeKG in a project, adding code-kg as a Poetry dependency, building the SQLite or LanceDB knowledge graph, configuring .mcp.json for Claude Code, configuring claude_desktop_config.json for Claude Desktop, using the codekg-mcp CLI, running codekg-build-sqlite or codekg-build-lancedb, using the graph_stats / query_codebase / pack_snippets / get_node MCP tools, or troubleshooting CodeKG errors.
---

# CodeKG Skill

CodeKG indexes Python repos into a hybrid knowledge graph (SQLite + LanceDB) and exposes it as MCP tools for AI agents.

## Installation (Poetry)

```bash
# With MCP server support
poetry add "code-kg[mcp] @ git+https://github.com/suchanek/code_kg.git"
```

Adds to `pyproject.toml`:
```toml
code-kg = { git = "https://github.com/suchanek/code_kg.git", extras = ["mcp"] }
```

## Build the Knowledge Graph

```bash
# Step 1 — SQLite graph (flag: --db)
poetry run codekg-build-sqlite --repo . --db codekg.sqlite

# Step 2 — LanceDB vector index (flag: --sqlite, NOT --db)
poetry run codekg-build-lancedb --sqlite codekg.sqlite --lancedb ./lancedb
```

> **Common mistake:** `codekg-build-lancedb` uses `--sqlite`, not `--db`.

Add `--wipe` to either command to rebuild from scratch.

## Configure Claude Code (.mcp.json)

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
      ]
    }
  }
}
```

Always use **absolute paths**. Merge into existing `mcpServers` — don't overwrite other entries.

## Configure Claude Desktop (claude_desktop_config.json)

Claude Desktop has no Poetry on PATH — use the absolute venv binary:

```bash
poetry env info --path
# → /path/to/venv
# binary: /path/to/venv/bin/codekg-mcp
```

Config path: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)

```json
{
  "mcpServers": {
    "codekg": {
      "command": "/path/to/venv/bin/codekg-mcp",
      "args": ["--repo", "/abs/path", "--db", "/abs/path/codekg.sqlite", "--lancedb", "/abs/path/lancedb"]
    }
  }
}
```

## Automated Setup

If the project has Claude Copilot installed:
```
/setup-mcp /path/to/repo
```
This installs, builds, smoke-tests, and writes both config files automatically.

## MCP Tools

| Tool | When to use |
|---|---|
| `graph_stats()` | First call — understand codebase size/shape |
| `query_codebase(q)` | Explore graph structure, find relevant nodes |
| `pack_snippets(q)` | Read actual source code (prefer over query_codebase) |
| `get_node(node_id)` | Fetch metadata for a specific node by ID |

## Query Strategy Guide

### Choosing `k` and `hop`

| Goal | Settings |
|---|---|
| Narrow, precise lookup | `k=4, hop=0` |
| Standard exploration | `k=8, hop=1` (default) |
| Broad context sweep | `k=12, hop=2` |
| Deep dependency trace | `k=8, hop=2, rels="CALLS,IMPORTS"` |

### Choosing `rels`

| Relation | When to include |
|---|---|
| `CONTAINS` | Almost always — structural context |
| `CALLS` | Tracing execution flow |
| `IMPORTS` | Dependency analysis |
| `INHERITS` | OOP hierarchy |

### Typical session workflow

```
1. graph_stats()                                    → orientation
2. query_codebase("auth flow", k=8, hop=1)          → find nodes
3. pack_snippets("JWT validation", k=6, hop=1)      → read source
4. get_node("fn:src/auth/jwt.py:JWTValidator.validate")  → node detail
5. pack_snippets("error handling", k=4, hop=2, rels="CALLS")  → deeper
```

## Key Defaults

- `k=8, hop=1, rels="CONTAINS,CALLS,IMPORTS,INHERITS"`
- Node ID format: `<kind>:<module_path>:<qualname>` (e.g. `fn:src/auth/jwt.py:JWTValidator.validate`)
- Node ID prefixes: `mod:` module, `cls:` class, `fn:` function/method, `sym:` external symbol
- Transport: `stdio` (Claude Code/Desktop), `sse` (HTTP clients)

## Troubleshooting

| Error | Fix |
|---|---|
| `error: the following arguments are required: --sqlite` | Use `--sqlite`, not `--db`, for `codekg-build-lancedb` |
| `ERROR: 'mcp' package not found` | `poetry add mcp` |
| `WARNING: SQLite database not found` | Run both build commands first |
| MCP server not appearing | Use absolute paths; restart Claude Code |
| Empty query results | Run `codekg-build-lancedb --wipe` |

## Full Reference

See `references/installation.md` for complete CLI flags, `.mcp.json` templates with full Copilot stack, gitignore recommendations, and query strategy guide.
