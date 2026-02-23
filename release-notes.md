## CodeKG v0.2.1

> **Data-flow graph edges, Jina v3 embeddings, and agent tooling**

This release adds a third AST pass that captures how data moves through your code, upgrades the default embedding model for significantly richer semantic search, and ships new agent tooling for zero-friction knowledge graph rebuilds.

---

### Highlights

#### Data-Flow Graph (Pass 3)

The knowledge graph now tracks data movement alongside structure and call graphs. A new `CodeKGVisitor` runs a third AST pass and emits four new edge types:

| Edge | Meaning |
|------|---------|
| `READS` | A function reads a variable or parameter |
| `WRITES` | A function writes (assigns) a variable |
| `ATTR_ACCESS` | An attribute is accessed on an object |
| `DEPENDS_ON` | A derived dependency relationship |

This makes queries like *"what does this function read?"* or *"which methods write to this field?"* precise and grounded — not inferred from call graphs.

Scope tracking is exact: `_seed_params` pre-populates function scope with all parameters (positional, keyword-only, `*args`, `**kwargs`), preventing spurious `READS` edges on parameter names. Async functions (`async def`) receive full scope treatment via `visit_AsyncFunctionDef`.

#### Jina v3 Embeddings

The default embedding model upgrades from `all-MiniLM-L6-v2` (384-dim) to `jinaai/jina-embeddings-v3` (1024-dim). Semantic search results are noticeably richer, especially for nuanced queries about code behaviour.

The model name is centralised in a `DEFAULT_MODEL` constant and overridable via the `CODEKG_MODEL` environment variable — no code changes needed to swap models.

#### `/codekg-rebuild` Slash Command

A new Claude Code slash command guides agents through a complete wipe-and-rebuild of the SQLite knowledge graph and LanceDB semantic index for any repository. Covers path resolution, `--wipe` builds of both layers, index verification, and a structured summary report.

#### Query Cheatsheet

`docs/CHEATSHEET.md` is a reference card for all four MCP tools, covering:
- Worked examples for `graph_stats`, `query_codebase`, `pack_snippets`, `get_node`
- Data-flow query patterns using the new edge types
- Full edge type reference table
- Parameter quick reference

A copy is bundled inside the CodeKG skill at `.claude/skills/codekg/references/CHEATSHEET.md` for agent-side access.

---

### What's New

- **`src/code_kg/visitor.py`** — `CodeKGVisitor` for scope-aware data-flow extraction
- **`src/code_kg/codekg.py`** — `DEFAULT_MODEL` constant; four new `EDGE_KINDS`; `.codekg/` excluded from AST traversal; Pass 3 integration in `extract_repo()`
- **`src/code_kg/index.py`** — `trust_remote_code=True` for Jina v3; embedding dimension fallback updated to 1024
- **`pyproject.toml`** — `einops ^0.8.2` and `transformers >=4.44,<5.0` added as runtime dependencies (required by Jina v3)
- **`tests/test_visitor.py`** — 158-line test suite covering scope management, assignment tracking, and `READS`/`WRITES`/`ATTR_ACCESS` edge emission
- **`.claude/commands/codekg-rebuild.md`** — `/codekg-rebuild` slash command
- **`docs/CHEATSHEET.md`** — Public query cheatsheet
- **`README.md`** — Caller Lookup section documenting bidirectional edge traversal; Development section with clone + install workflow

### Removed

- **Docker infrastructure** (`Dockerfile`, `docker-compose.yml`, `.dockerignore`, `docs/docker.md`) — superseded by direct pip / Poetry install
- **Legacy design documents** (`docs/code_kg.pdf`, `docs/code_kg.md`, `docs/code_kg.tex`) — superseded by `docs/Architecture.md` and `docs/CHEATSHEET.md`

---

### Installation

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Flux-Frontiers/code_kg/main/scripts/install-skill.sh)
```

Or to reinstall / update an existing deployment:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Flux-Frontiers/code_kg/main/scripts/install-skill.sh) --wipe
```

See the [README](README.md) for full usage and configuration details.
