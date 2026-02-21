## CodeKG v0.1.0

> **AI Integration Layer for Python Codebase Intelligence**

CodeKG indexes Python codebases into a hybrid SQLite + LanceDB knowledge graph and exposes it to AI agents via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). This first release ships a polished installer, a full CI/CD pipeline, and distribution via GitHub Releases wheels.

---

### Highlights

#### One-Command AI Integration Layer

`scripts/install-skill.sh` is now a full AI integration layer installer. A single command wires CodeKG into your choice of MCP clients:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/suchanek/code_kg/main/scripts/install-skill.sh)
```

Supported providers (select with `--providers`):

| Flag | Provider |
|------|----------|
| `claude` | Claude Code |
| `kilo` | Kilo Code |
| `copilot` | GitHub Copilot (VS Code) |
| `cline` | Cline |
| `all` | All of the above (default) |

New installer flags:

- **`--providers claude,kilo`** — configure only the providers you use
- **`--dry-run`** — print every action without making any changes
- **`--wipe`** — force a full rebuild of the SQLite graph and LanceDB index

#### GitHub Releases Distribution

CodeKG is distributed as a wheel via GitHub Releases (not PyPI — the PolyForm NC license is not compatible with the PyPI terms of service). The installer automatically downloads and installs the latest release wheel, with fallback to `pip install @ git+https://…` and then `poetry add` for Poetry-managed repos.

#### CI/CD Pipeline

- **CI** (`.github/workflows/ci.yml`): runs on every push and PR to `main` — ruff format/lint, mypy type-check, and pytest across Python 3.10, 3.11, and 3.12.
- **Publish** (`.github/workflows/publish.yml`): triggered by `v*` tags — runs tests, builds wheel + sdist via `poetry build`, and creates a GitHub Release with both artifacts attached.

#### Pre-commit Hooks

`.pre-commit-config.yaml` ships with the repo:

- `ruff` lint + format on every commit
- trailing-whitespace and end-of-file fixers
- YAML and TOML validation
- merge-conflict detection
- large-file guard (1 MB, docs/ binaries excluded)
- debug-statement detection

---

### MCP Tools

| Tool | Description |
|------|-------------|
| `graph_stats` | Node/edge counts broken down by kind |
| `query_codebase` | Hybrid semantic + graph traversal over the knowledge graph |
| `pack_snippets` | Source-grounded snippet extraction with line numbers |
| `get_node` | Fetch a single node by stable ID |

---

### Installation

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/suchanek/code_kg/main/scripts/install-skill.sh)
```

See the [README](README.md) for full usage and configuration details.

---

### What's Next

- Incremental graph updates (re-index changed files only)
- Cross-repo linking
- Support for additional languages beyond Python
