# Release Notes — v0.2.3

> Released: 2026-02-23

### Added

- **`.claude/commands/codekg-rebuild.md`** — New `/codekg-rebuild` slash command that wipes and rebuilds the CodeKG SQLite knowledge graph and LanceDB semantic index for any repository. Guides the agent through path resolution, `--wipe` builds of both layers, verification, and a structured summary report.
- **`docs/CHEATSHEET.md`** — Public-facing CodeKG query cheatsheet covering all four MCP tools (`graph_stats`, `query_codebase`, `pack_snippets`, `get_node`) with worked examples, data-flow query patterns, edge type reference table, parameter quick reference, and live codebase stats.
- **`.claude/skills/codekg/references/CHEATSHEET.md`** — Skill-level copy of the cheatsheet, co-located with the CodeKG skill for agent-side reference.
- **`README.md` — Caller Lookup section** — Documents bidirectional edge traversal in `expand()` for precise reverse call lookup.
- **`README.md` — Development section** — Clone + `poetry install --extras mcp` + `pytest` workflow for contributors.

### Changed

- **`scripts/install-skill.sh`** — New Step 2 installs both Claude Code slash commands (`codekg.md`, `codekg-rebuild.md`) to `~/.claude/commands/`, copying from the local repo or downloading from GitHub. Subsequent steps renumbered (3→4 through 7→8). Final summary now reports installed commands. Variable renamed `LOCAL_CMD` → `_LOCAL_CMD` to avoid collision with the new loop variable.
- **`README.md`** — `symbol` node description updated to mention the data-flow pass; `ATTR_ACCESS`, `READS`, and `WRITES` edge types added to the edges table; Phase 1 description expanded to cover the three sequential AST passes; embedding model updated to `jinaai/jina-embeddings-v3` in CLI examples; Installation section restructured (pip-first, Poetry simplified); MCP configuration section headings clarified; `visitor.py` added to file structure listing; redundant dev-workflow callouts removed.

### Removed

- **`docs/code_kg.pdf`** — Legacy PDF removed; superseded by `docs/CHEATSHEET.md` and `docs/Architecture.md`.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
