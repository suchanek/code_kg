# Release Notes — v0.3.0

> Released: 2026-02-23

### Added

- **`GraphStore.resolve_symbols()`** (`store.py`) — Post-build step that adds `RESOLVES_TO` edges from `sym:` stub nodes to their matching first-party definitions (`fn:`, `cls:`, `m:`, `mod:`) by name. Called automatically after `GraphStore.write()` in `CodeKG.build_graph()` and `codekg-build-sqlite`. Enables fan-in queries across module boundaries by connecting import-alias call sites to their canonical definition nodes. Idempotent.
- **`GraphStore.callers_of(node_id, *, rel="CALLS")`** (`store.py`) — Two-phase reverse lookup (fan-in): returns direct incoming `rel` edges plus callers that reach the target through `sym:` stubs resolved via `RESOLVES_TO`. Returns deduplicated caller node dicts.
- **`CodeKG.callers(node_id, *, rel="CALLS")`** (`kg.py`) — Thin orchestrator-level wrapper around `GraphStore.callers_of()`.
- **`callers(node_id, rel)` MCP tool** (`mcp_server.py`) — New fifth tool exposing precise fan-in lookup to agents. Returns JSON with `node_id`, `rel`, `caller_count`, and `callers` list. Cross-module callers (those referencing the target via an import alias) are resolved automatically.
- **`RESOLVES_TO` edge relation** — New graph edge type linking `sym:` stubs to in-repo definitions. Not emitted by the AST extractor; added by `resolve_symbols()` post-build.
- **`article/code_kg.tex`** — LaTeX source for the technical paper "CodeKG: Deterministic Code Navigation via Knowledge Graphs, Semantic Indexing, and Grounded Context Packing". Covers the four-layer architecture, hybrid query model, fan-in lookup, and a detailed comparison with Microsoft GraphRAG (Structural KG-RAG).
- **`article/code_kg_medium.md`** — Medium.com companion article "Your Codebase Has a Shape. Most Tools Can't See It." — an accessible overview of CodeKG's design, query model, and MCP integration.
- **`article/logo.png`** — Project logo added to the `article/` directory alongside the paper assets.

### Changed

- **`build_codekg_sqlite.py`** — Now calls `store.resolve_symbols()` after `store.write()` and reports the resolved edge count in the output line (`resolved=N`).
- **`docs/Architecture.md`** — Updated to document `RESOLVES_TO`, `resolve_symbols()`, `callers_of()`, `callers()`, the updated build pipeline data flow, and the new MCP tool.
- **`docs/MCP.md`** — Added `callers` tool reference section, updated overview (4 → 5 tools), added fan-in step to the typical workflow, updated summary table.
- **`.claude/skills/codekg/SKILL.md`** — Added `callers` to tools table and workflow; added `RESOLVES_TO` to rels reference.
- **`README.md`** — Added `RESOLVES_TO` edge to the edges table; expanded "Caller Lookup" section to "Caller Lookup (Fan-In)" with two-phase lookup explanation and code examples; added symbol resolution as build pipeline step 4; added `callers(node_id)` to the MCP tools table; updated docs file structure listing.

### Removed

- **`docs/code_kg.pdf`** — Moved to `article/code_kg.pdf` alongside the paper source.

### Fixed

- **`SemanticIndex._open_table()` LanceDB wipe bug** (`index.py`) — When `wipe=True`, the table is now dropped and recreated instead of deleting rows from the existing table. Row deletion preserved the stale schema, causing an Arrow `ListType → FixedSizeListType` cast error on the first `tbl.add()` call after an embedding model change. Dropping the table ensures a clean schema on every wipe.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
