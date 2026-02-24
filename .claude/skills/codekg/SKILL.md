---
name: codekg
description: Expert knowledge for installing, configuring, and using the CodeKG MCP server — a hybrid semantic + structural knowledge graph for Python codebases. Use this skill when the user asks about: setting up CodeKG in a project, adding code-kg as a Poetry dependency, building the SQLite or LanceDB knowledge graph, configuring .mcp.json for Claude Code or Kilo Code, configuring .vscode/mcp.json for GitHub Copilot, configuring claude_desktop_config.json for Claude Desktop, configuring Cline MCP settings, using the codekg-mcp CLI, running codekg-build-sqlite or codekg-build-lancedb, using the graph_stats / query_codebase / pack_snippets / get_node / callers MCP tools, or troubleshooting CodeKG errors.
---

# CodeKG Skill

> **Use CodeKG first — before grep, Glob, or file reads.**
>
> Grep and file search find text. CodeKG understands code. It knows what calls what, what inherits from what, which modules are imported where, and surfaces the most semantically relevant source snippets in a single query. One `pack_snippets` call replaces five rounds of grep-and-read and gives the agent real structural insight into the codebase — not just line matches.

CodeKG indexes Python repos into a hybrid knowledge graph (SQLite + LanceDB) and exposes it as MCP tools for AI agents.

## Installation (Poetry)

```bash
# With MCP server support
poetry add "code-kg[mcp] @ git+https://github.com/Flux-Frontiers/code_kg.git"
```

Adds to `pyproject.toml`:
```toml
code-kg = { git = "https://github.com/Flux-Frontiers/code_kg.git", extras = ["mcp"] }
```

## Build the Knowledge Graph

```bash
# Step 1 — SQLite graph
poetry run codekg-build-sqlite --repo .

# Step 2 — LanceDB vector index
poetry run codekg-build-lancedb --repo .
```

> **Common mistake:** `codekg-build-lancedb` uses `--sqlite`, not `--db`, when specifying a non-default path.

Add `--wipe` to either command to rebuild from scratch.

## Rebuilding After Code Changes

The knowledge graph is a snapshot of the codebase at build time. It does **not** update automatically. Stale data causes misleading query results — especially after renames, deletions, or large refactors.

### When to rebuild

| Change | Action |
|---|---|
| Added / renamed / deleted functions, classes, or modules | Full rebuild (`--wipe`) |
| Large refactor touching many files | Full rebuild (`--wipe`) |
| Minor edits within existing functions | Incremental rebuild (no `--wipe`) is usually sufficient |
| New file added to the repo | Incremental rebuild is sufficient |

> **Why `--wipe` matters:** Without it, deleted or renamed nodes remain in the index as phantom entries. LanceDB upserts by node ID so renamed nodes leave behind orphans; `--wipe` clears them.

### Full rebuild (recommended after significant changes)

```bash
# Poetry
poetry run codekg-build-sqlite  --repo . --wipe
poetry run codekg-build-lancedb --repo . --wipe

# python -m (pip-installed)
python -m code_kg build-sqlite  --repo . --wipe
python -m code_kg build-lancedb --repo . --wipe
```

### Incremental rebuild (minor additions only)

```bash
# Poetry — omit --wipe to upsert without clearing
poetry run codekg-build-sqlite  --repo .
poetry run codekg-build-lancedb --repo .
```

### Using the installer script

```bash
# Re-run the installer with --wipe from your target repo
bash scripts/install-skill.sh --wipe

# Or via curl if not running from a local clone
curl -fsSL https://raw.githubusercontent.com/Flux-Frontiers/code_kg/main/scripts/install-skill.sh \
  | bash -s -- --wipe
```

---

## Configure Claude Code / Kilo Code (.mcp.json)

Both Claude Code and Kilo Code read per-repo config from `.mcp.json` in the project root.

```json
{
  "mcpServers": {
    "codekg": {
      "command": "poetry",
      "args": [
        "run", "codekg-mcp",
        "--repo",    "/absolute/path/to/repo",
        "--db",      "/absolute/path/to/repo/.codekg/graph.sqlite",
        "--lancedb", "/absolute/path/to/repo/.codekg/lancedb"
      ],
      "env": {
        "POETRY_VIRTUALENVS_IN_PROJECT": "false"
      }
    }
  }
}
```

Always use **absolute paths**. Merge into existing `mcpServers` — don't overwrite other entries.

> ⚠️ Do NOT add `codekg` to any global settings file — use per-repo `.mcp.json` only.

## Configure GitHub Copilot (.vscode/mcp.json)

GitHub Copilot uses a different schema — `"servers"` key and `"type": "stdio"` required:

```json
{
  "servers": {
    "codekg": {
      "type": "stdio",
      "command": "poetry",
      "args": [
        "run", "codekg-mcp",
        "--repo",    "/absolute/path/to/repo",
        "--db",      "/absolute/path/to/repo/.codekg/graph.sqlite",
        "--lancedb", "/absolute/path/to/repo/.codekg/lancedb"
      ],
      "env": {
        "POETRY_VIRTUALENVS_IN_PROJECT": "false"
      }
    }
  }
}
```

VS Code will prompt you to **Trust** the server on first use.

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
      "args": ["--repo", "/abs/path", "--db", "/abs/path/.codekg/graph.sqlite", "--lancedb", "/abs/path/.codekg/lancedb"]
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
| `callers(node_id)` | Find all callers of a node — fan-in lookup resolving cross-module sym: stubs |

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
| `RESOLVES_TO` | Connecting `sym:` stubs to definitions | Used internally by `callers()` — include in `query_codebase` rels for graph traversal through import aliases |

### Typical session workflow

```
1. graph_stats()                                    → orientation
2. query_codebase("auth flow", k=8, hop=1)          → find nodes
3. pack_snippets("JWT validation", k=6, hop=1)      → read source
4. get_node("fn:src/auth/jwt.py:JWTValidator.validate")  → node detail
5. callers("fn:src/auth/jwt.py:JWTValidator.validate")   → all callers, cross-module included
6. pack_snippets("error handling", k=4, hop=2, rels="CALLS")  → deeper
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
