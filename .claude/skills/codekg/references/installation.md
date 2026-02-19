# CodeKG Installation Reference

## Table of Contents
1. [CLI Flags Reference](#cli-flags-reference)
2. [Full .mcp.json Templates](#full-mcpjson-templates)
3. [Query Strategy Guide](#query-strategy-guide)
4. [Gitignore Recommendations](#gitignore-recommendations)
5. [Smoke-Test Commands](#smoke-test-commands)
6. [Full Troubleshooting Table](#full-troubleshooting-table)

---

## CLI Flags Reference

### `codekg-build-sqlite`

| Flag | Required | Default | Description |
|---|---|---|---|
| `--repo` | ✓ | — | Repository root path |
| `--db` | ✓ | — | SQLite output path |
| `--wipe` | | false | Delete existing graph first |

### `codekg-build-lancedb`

| Flag | Required | Default | Description |
|---|---|---|---|
| `--sqlite` | ✓ | — | Path to `codekg.sqlite` (**not** `--db`) |
| `--lancedb` | ✓ | — | LanceDB output directory |
| `--table` | | `codekg_nodes` | LanceDB table name |
| `--model` | | `all-MiniLM-L6-v2` | Sentence-transformer model |
| `--wipe` | | false | Delete existing vectors first |
| `--kinds` | | `module,class,function,method` | Node kinds to embed |
| `--batch` | | `256` | Embedding batch size |

### `codekg-mcp`

| Flag | Default | Description |
|---|---|---|
| `--repo` | `.` | Repository root |
| `--db` | `codekg.sqlite` | SQLite path |
| `--lancedb` | `./lancedb` | LanceDB directory |
| `--model` | `all-MiniLM-L6-v2` | Embedding model |
| `--transport` | `stdio` | `stdio` or `sse` |

### `codekg-query`

```bash
poetry run codekg-query \
  --sqlite codekg.sqlite \
  --lancedb ./lancedb \
  --q "your query here"
```

---

## Full .mcp.json Templates

### Minimal (codekg only)

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

### Full Claude Copilot stack

```json
{
  "mcpServers": {
    "copilot-memory": {
      "command": "node",
      "args": ["/Users/YOU/.claude/copilot/mcp-servers/copilot-memory/dist/index.js"],
      "env": {
        "MEMORY_PATH": "/Users/YOU/.claude/memory",
        "WORKSPACE_ID": "your-project"
      }
    },
    "skills-copilot": {
      "command": "node",
      "args": ["/Users/YOU/.claude/copilot/mcp-servers/skills-copilot/dist/index.js"],
      "env": {
        "LOCAL_SKILLS_PATH": "./.claude/skills"
      }
    },
    "task-copilot": {
      "command": "node",
      "args": ["/Users/YOU/.claude/copilot/mcp-servers/task-copilot/dist/index.js"],
      "env": {
        "TASK_DB_PATH": "/Users/YOU/.claude/tasks",
        "WORKSPACE_ID": "your-project"
      }
    },
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

### Claude Desktop (absolute venv path)

```json
{
  "mcpServers": {
    "codekg": {
      "command": "/path/to/venv/bin/codekg-mcp",
      "args": [
        "--repo",    "/absolute/path/to/repo",
        "--db",      "/absolute/path/to/repo/codekg.sqlite",
        "--lancedb", "/absolute/path/to/repo/lancedb"
      ]
    }
  }
}
```

Get venv path: `poetry env info --path`

---

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

### Node ID format

`<kind>:<module_path>:<qualname>`

| Prefix | Kind |
|---|---|
| `mod:` | module |
| `cls:` | class |
| `fn:` | function / method |
| `sym:` | unresolved external symbol |

---

## Gitignore Recommendations

```gitignore
codekg.sqlite
codekg.sqlite-shm
codekg.sqlite-wal
lancedb/
```

---

## Smoke-Test Commands

```bash
# Graph stats (Python API)
poetry run python -c "
from code_kg import CodeKG
import json
kg = CodeKG(repo_root='.', db_path='codekg.sqlite', lancedb_dir='./lancedb')
print(json.dumps(kg.stats(), indent=2))
"

# Sample query (CLI)
poetry run codekg-query --sqlite codekg.sqlite --lancedb ./lancedb --q "module structure"

# Verify SQLite row counts
sqlite3 codekg.sqlite "SELECT COUNT(*) FROM nodes; SELECT COUNT(*) FROM edges;"
```

---

## Full Troubleshooting Table

| Symptom | Cause | Fix |
|---|---|---|
| `error: the following arguments are required: --sqlite` | Wrong flag for lancedb builder | Use `--sqlite`, not `--db` |
| `ERROR: 'mcp' package not found` | Optional dep missing | `poetry add mcp` |
| `WARNING: SQLite database not found` | Graph not built | Run `codekg-build-sqlite` first |
| Empty results from `query_codebase` | LanceDB stale or missing | `codekg-build-lancedb --wipe` |
| `RuntimeError: CodeKG not initialised` | Server not started via CLI | Always use `codekg-mcp` CLI |
| Snippets show wrong line numbers | Source changed since build | `codekg-build-sqlite --wipe` |
| MCP server not in Claude Code | Relative paths or wrong location | Absolute paths in `.mcp.json`; restart |
| MCP server not in Claude Desktop | Wrong binary path | `poetry env info --path` for absolute path |
| `poetry run which codekg-mcp` empty | `mcp` extra not installed | `poetry add "code-kg[mcp]"` |
