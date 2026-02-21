# CodeKG — Cline Rules Template

Copy this file to `.clinerules` in the root of any repo that has CodeKG configured.
It gives Cline automatic context about the available MCP tools and how to use them.

---

## How to use this file

```bash
cp /path/to/code_kg/.claude/skills/codekg/clinerules.md /path/to/myrepo/.clinerules
```

Or add the content below to an existing `.clinerules` file in your repo.

---

## Content to put in `.clinerules`

```
## CodeKG MCP Tools

This project has a CodeKG MCP server configured (`codekg`). Use these tools to
explore the codebase structure before writing or modifying code.

### Available tools

- **graph_stats()** — Get codebase size and shape (node/edge counts by type).
  Use this first to orient yourself in a new session.

- **query_codebase(q)** — Hybrid semantic + structural search. Returns nodes
  (modules, classes, functions, methods) and their relationships. Use for:
  - Finding where something is implemented
  - Understanding call graphs and dependencies
  - Exploring module structure

- **pack_snippets(q)** — Like query_codebase but returns actual source code
  snippets. Use when you need to read the implementation, not just the structure.

- **get_node(node_id)** — Look up a single node by its ID (e.g.
  `fn:src/mymodule.py:my_function`). Use after query_codebase to get details.

### When to use CodeKG

- **Start of session:** Call `graph_stats()` to understand the codebase size.
- **Before editing:** Call `query_codebase("relevant topic")` to find related code.
- **Before implementing:** Call `pack_snippets("feature area")` to read existing patterns.
- **Tracing calls:** Use `query_codebase` with function/class names to find callers/callees.

### Rebuilding the index

If the codebase has changed significantly, rebuild with:

```bash
poetry run codekg-build-sqlite  --repo . --db .codekg/graph.sqlite --wipe
poetry run codekg-build-lancedb --sqlite .codekg/graph.sqlite --lancedb .codekg/lancedb --wipe
```

### Cline MCP config

Cline uses a global config file (not per-repo `.mcp.json`):
`~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

Add a named entry for each repo:
```json
{
  "mcpServers": {
    "codekg-REPONAME": {
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

Use a unique name per repo (e.g. `codekg-myproject`) to avoid conflicts.
Enable/disable servers via the Cline MCP panel as you switch projects.
```
