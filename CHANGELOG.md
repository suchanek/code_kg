# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`.github/actions/codekg-action/`** — GitHub composite action for automated CodeKG analysis. Builds SQLite + LanceDB indexes, runs architectural analysis, caches the `.codekg/` directory, uploads artifacts, optionally posts PR comments, and can fail the workflow when issues are detected. Configurable via `python-version`, `repo-path`, `report-path`, `json-path`, `model`, `post-comment`, and `fail-on-issues` inputs.
- **`_get_report_metadata()` method** (`codekg_thorough_analysis.py`) — Generates a Markdown metadata block with generation timestamp (UTC), CodeKG package version, Git commit SHA (7-char short form), and branch. Falls back gracefully to "unknown" when Git is unavailable or running outside a Git repository. Detects CI environment variables (`GITHUB_SHA`, `GITHUB_REF`) for accurate metadata in GitHub Actions workflows.
- **`trame-vtk` dependency** (`pyproject.toml`) — Added optional visualization dependency for enhanced 3D rendering capabilities.

### Changed

- **DateTime handling** (`codekg_thorough_analysis.py`) — All datetime calls upgraded to use `datetime.datetime.now(datetime.timezone.utc)` for consistent UTC timestamps across local, CI, and cloud environments. Affects `_write_report()`, `main()`, `_default_report_name()`, and JSON snapshot generation.
- **Report generation** (`codekg_thorough_analysis.py`) — Markdown report now includes metadata block at the top (timestamp, version, commit ref) prepended to the analysis sections.
- **CLI error handling** (`codekg_thorough_analysis.py`) — `cli()` function wrapped in try-except, logging exceptions and exiting with status code 1 on failure. Explicit `sys.exit(0)` added on success.
- **3D visualization enhancements** (`viz3d.py`, `layout3d.py`) — Node sizes doubled for improved visibility (module: 0.6→1.2, class: 0.45→0.9, function: 0.35→0.7, method: 0.25→0.5, symbol: 0.2→0.4). Ground plane and cake stand geometry added to create_kg_visualization(). CONTAINS edge color darkened (#BDC3C7→#555555). Removed unused QTimer import and "Spin" button reference. Code formatting updated to ruff standards.
- **PyVista dependency** (`pyproject.toml`) — Added `jupyter` extras to enable enhanced PyVista features.
- **LayerCakeLayout default parameter** (`layout3d.py`) — Disc radius increased from 18.0 to 28.0 for better node spacing.

### Removed

### Fixed

---

## [0.3.2] - 2026-02-25

### Added

- **`scripts/rebuild-codekg.sh`** — Script to rebuild the SQLite knowledge graph and LanceDB semantic index on demand (invoked manually or via `/codekg-rebuild`).
- **`docs/analysis_v0.3.1.md`** — Versioned CodeKG architecture analysis (complexity hotspots, call chains, module coupling, orphaned code) stamped with v0.3.1.
- **Step 4c in `/release` workflow** (`.claude/commands/release.md`) — Rebuilds the index, runs `codekg-analyze`, writes `docs/analysis_v<version>.md`, and re-stages `.codekg/` artifacts as part of every release.
- **Cline MCP settings support** (`scripts/install-skill.sh`) — Installer now writes a repo-keyed entry (`codekg-<repo-name>`) to Cline's global `cline_mcp_settings.json` and installs `setup-mcp.md` as a Claude command.

### Fixed

- **Removed `codekg-rebuild` pre-commit hook** (`.pre-commit-config.yaml`) — The hook generated new `.codekg/` artifacts on every commit attempt, causing a dirty-working-tree loop. Rebuild is now a manual step via `scripts/rebuild-codekg.sh` or `/codekg-rebuild`.
- **`.codekg/` WAL files cleaned up** — Stale `graph.sqlite-shm` and `graph.sqlite-wal` write-ahead log files removed from the committed index.

### Changed

- **`CodeKG.__init__`** (`kg.py`) — `db_path` and `lancedb_dir` are now optional; both default to `<repo_root>/.codekg/graph.sqlite` and `<repo_root>/.codekg/lancedb`. Existing callers that pass explicit paths continue to work unchanged.
- **All CLI commands and MCP configs** (`codekg-rebuild.md`, `setup-mcp.md`, `install-skill.sh`, `README.md`) — Simplified to `--repo`-only invocation; `--db`, `--sqlite`, and `--lancedb` flags are now optional everywhere.
- **`.gitignore`** — Removed `.codekg/` so the pre-built knowledge graph and vector index are committed with the repo, enabling zero-setup MCP after cloning.
- **`README.md`** — Updated all CLI examples to reflect optional flags; added manual Cline setup instructions with repo-keyed server naming; simplified `.mcp.json` examples to use `poetry run`.

### Added

- **`_default_report_name()`** (`codekg_thorough_analysis.py`) — Helper that derives a timestamped markdown filename (`<repo>_analysis_<YYYYMMDD>.md`) from the resolved repo root, used as the automatic output name when `--output` is not supplied.
- **`codekg-analyze` — zero-argument invocation** (`codekg_thorough_analysis.py`) — `repo_root` is now optional (defaults to `"."`); `db_path` and `lancedb_path` default to `.codekg/graph.sqlite` and `.codekg/lancedb` respectively, matching the standard project layout.
- **`codekg-analyze --output`/`-o`** — Writes the markdown analysis report to the specified path (auto-named when omitted).
- **`codekg-analyze --json`/`-j`** — Overrides the JSON snapshot output path (default: `~/.claude/codekg_analysis_latest.json`).
- **`codekg-analyze --quiet`/`-q`** — Suppresses the Rich console summary table, useful in CI or scripted contexts.
- **DB existence pre-flight check** (`codekg_thorough_analysis.py`) — `main()` now warns and exits early when the SQLite database file is not found, rather than raising a cryptic import or file error.
- **Startup path summary** (`codekg_thorough_analysis.py`) — `main()` prints the resolved repo, DB, LanceDB, and report paths before analysis begins for easier debugging.

### Changed

- **`cli()` upgraded to `argparse`** (`codekg_thorough_analysis.py`) — Replaced the manual `sys.argv` parser with `argparse.ArgumentParser` (using `ArgumentDefaultsHelpFormatter`), adding `--help` support and the new `--db`, `--lancedb`, `--output`, `--json`, and `--quiet` flags.
- **`main()` signature** (`codekg_thorough_analysis.py`) — All positional parameters are now keyword-only with sensible defaults; added `json_path` and `quiet`; JSON output variable renamed `output_file` → `json_out`.

### Removed

### Fixed

---

## [0.3.1] - 2026-02-24

### Added

- **`codekg-analyze` CLI entry point** (`pyproject.toml`) — New Poetry script exposing `codekg_thorough_analysis:cli` as the `codekg-analyze` command. Runs a comprehensive structural and semantic analysis of a CodeKG knowledge graph and saves results to `~/.claude/codekg_analysis_latest.json`.
- **`cli()` entry point** (`codekg_thorough_analysis.py`) — Zero-argument wrapper around `main()` that parses `sys.argv` for `<repo_root>`, `<db_path>`, and `<lancedb_path>`, enabling the module to be registered as a Poetry script entry point. `__main__` block updated to call `cli()`.
- **`README.md` — CLI Usage section 7** — Documents `codekg-analyze` usage, arguments, and output location.

---

## [0.3.0] - 2026-02-23

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

## [0.2.3] - 2026-02-23

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

## [0.2.2] - 2026-02-23

### Added

- **`docs/code_kg.pdf`** — Technical paper added to repository and linked from README.
- **`.claude/commands/release.md`** — New `/release` slash command for the release workflow.
- **`tests/test_index.py` — `test_semanticindex_open_table_existing`** — Regression test that exercises the "table already exists" branch of `_open_table`, ensuring the `list_tables().tables` API check is covered on every run.

### Changed

- **`src/code_kg/codekg.py`** — `DEFAULT_MODEL` reverted to `all-MiniLM-L6-v2` (384-dim); `jinaai/jina-embeddings-v3` caused GPU memory exhaustion on large repositories.
- **`src/code_kg/index.py`** — Removed `trust_remote_code=True` (not needed for MiniLM); embedding dimension fallback reverted to `384`.
- **`src/code_kg/app.py`** — `all-MiniLM-L6-v2` restored as the first (default) option in the embedding model selector.
- **`LICENSE`** — Switched from PolyForm Noncommercial 1.0.0 to Elastic License 2.0.
- **`README.md`** — Embedding model updated to `all-MiniLM-L6-v2` in Phase 2 description and CLI example; license badge and footer updated to Elastic 2.0; version badge updated to `0.2.2`; technical paper link added.
- **`docs/CHEATSHEET.md`** + **`.claude/skills/codekg/references/CHEATSHEET.md`** — Model in sample `graph_stats` output updated to `all-MiniLM-L6-v2`.
- **`release-notes.md`** — Added v0.2.2 section; jina references scrubbed from v0.2.1.
- **`.gitignore`** — Removed `*.pdf` exclusion so `docs/code_kg.pdf` is tracked.
- **`pyproject.toml`** + **`src/code_kg/__init__.py`** — Version bumped to `0.2.2`; lancedb dependency tightened to `>=0.29.0`; `einops` and `transformers` removed (were only required by jina v3).

---

## [0.2.1] - 2026-02-23

### Added

- **`src/code_kg/codekg.py` — `DEFAULT_MODEL` constant** — Sentence-transformer model name centralised in a single constant (`jinaai/jina-embeddings-v3`), overridable via the `CODEKG_MODEL` environment variable. Exported from the top-level `code_kg` package.
- **`src/code_kg/codekg.py` — data-flow edge kinds** — Four new edge relation types added to `EDGE_KINDS`: `READS`, `WRITES`, `ATTR_ACCESS`, `DEPENDS_ON`, extending the knowledge graph beyond structural edges.
- **`src/code_kg/codekg.py` — Pass 3 data-flow extraction** — `extract_repo()` now runs a third AST pass using `CodeKGVisitor` to emit data-flow edges (`READS`, `WRITES`, `ATTR_ACCESS`) alongside the existing structural and call-graph passes. New symbol/var nodes and edges are merged non-destructively.
- **`src/code_kg/visitor.py` — `visit_AsyncFunctionDef`** — Async functions now receive the same scope-tracking, parameter-seeding, and data-flow extraction treatment as synchronous functions.
- **`src/code_kg/visitor.py` — `_seed_params`** — All function/method parameters (positional, keyword-only, `*args`, `**kwargs`) are seeded into the local variable scope at function entry, preventing spurious `READS` edges for parameter names.
- **`tests/test_visitor.py`** — New test suite (158 lines) for `CodeKGVisitor`, covering scope management, assignment tracking, `READS`/`WRITES`/`ATTR_ACCESS` edge emission, and async function handling.
- **`pyproject.toml`** — Added `einops ^0.8.2` and `transformers >=4.44,<5.0` as runtime dependencies (required by `jinaai/jina-embeddings-v3`).

### Changed

- **Default embedding model** — Switched from `all-MiniLM-L6-v2` (384-dim) to `jinaai/jina-embeddings-v3` (1024-dim) across `index.py`, `kg.py`, `mcp_server.py`, and `app.py`. Fallback embedding dimension updated from 384 → 1024.
- **`src/code_kg/index.py` — `SentenceTransformerEmbedder`** — `trust_remote_code=True` passed to `SentenceTransformer` constructor to support models that ship custom pooling code (e.g. Jina v3).
- **`src/code_kg/visitor.py` — `_get_node_id`** — Now uses the project's canonical `kind:module:qualname` node-ID convention via `node_id()` from `codekg.py`, replacing a placeholder string identity.
- **`src/code_kg/visitor.py` — `_qualname`** — Simplified to use `current_scope[-1]` as the parent prefix, fixing spurious double-scoping.
- **`src/code_kg/codekg.py` — `SKIP_DIRS`** — Added `.codekg` to the set of directories excluded from AST traversal.
- **`src/code_kg/app.py`** — `jinaai/jina-embeddings-v3` added as the first (default) option in the embedding model selector.
- **`README.md`** — Version badge updated to `0.2.1`; Streamlit visualizer port corrected from `8501` to `8500`; Docker section and docker-related project structure entries removed.
- **`docs/Architecture.md`** — Docker Image section removed; Streamlit visualizer port corrected from `8501` to `8500`; Docker files removed from source layout listing.
- **`docs/deployment.md`** — Fly.io `internal_port` corrected from `8501` to `8500`.
- **`pyproject.toml`** + **`src/code_kg/__init__.py`** — Version bumped to `0.2.1`.
- **`tests/test_index.py`** — Updated assertion for `SentenceTransformerEmbedder` initialisation to expect `trust_remote_code=True`.

### Removed

- **`docker/Dockerfile`** + **`docker/docker-compose.yml`** + **`.dockerignore`** — Docker deployment infrastructure removed entirely.
- **`docs/docker.md`** — Docker setup reference removed.
- **`docs/code_kg.md`** + **`docs/code_kg.tex`** + **`docs/code_kg_medium.md`** — Legacy design documents and LaTeX source removed; architecture is covered by `docs/Architecture.md`.

---

## [0.2.0] - 2026-02-21

### Added

- **`src/code_kg/__main__.py`** — Subcommand dispatcher enabling `python -m code_kg <subcommand>` invocation without an activated venv. Maps `build-sqlite`, `build-lancedb`, `query`, `pack`, `viz`, and `mcp` to their respective `main()` entry points; rewrites `sys.argv` so each module's argparse sees the correct `prog` name in `--help` output.
- **`src/code_kg/mcp_server.py`** — MCP server exposing `graph_stats`, `query_codebase`, `pack_snippets`, and `get_node` tools for AI agent integration via the Model Context Protocol. `query_codebase` now accepts a `max_nodes` parameter (default 25) that caps the number of nodes returned, preventing unbounded result sets from flooding agent context windows.
- **`src/code_kg/graph.py`** — `CodeGraph`: OOP wrapper around `extract_repo()` providing a cached, chainable interface to pure AST extraction with no side effects.
- **`src/code_kg/store.py`** — `GraphStore`: SQLite persistence layer replacing the removed `codekg_sqlite.py`; exposes `write()`, `query_neighbors()`, and provenance-aware graph traversal via `ProvMeta`.
- **`src/code_kg/index.py`** — `SemanticIndex` + pluggable `Embedder` abstraction replacing `codekg_lancedb.py`; includes `SentenceTransformerEmbedder` and `SeedHit` result type for typed semantic search results.
- **`src/code_kg/kg.py`** — `CodeKG` top-level orchestrator owning the full pipeline (repo → `CodeGraph` → `GraphStore` → `SemanticIndex` → results); defines structured result types `BuildStats`, `QueryResult`, `Snippet`, and `SnippetPack`.
- **`tests/test_index.py`** — Comprehensive test suite (348 lines) covering `Embedder` ABC, `SentenceTransformerEmbedder` (fully mocked), `_build_index_text`, `_escape`, `_extract_distance`, and `SemanticIndex` build/search/cache integration tests using a lightweight `FakeEmbedder`.
- **`tests/test_graph.py`**, **`tests/test_kg.py`**, **`tests/test_store.py`** — Full unit test suites for the three new layered classes.
- **`.github/workflows/ci.yml`** — CI pipeline: ruff format/lint, mypy type-check, and pytest on every push and PR to `main`.
- **`.github/workflows/publish.yml`** — Release workflow: triggered on `v*` tags; runs tests, builds wheel + sdist via `poetry build`, and creates a GitHub Release with both artifacts attached. Distribution via GitHub Releases (not PyPI).
- **`.pre-commit-config.yaml`** — Pre-commit hooks: trailing-whitespace, end-of-file-fixer, YAML/TOML validation, merge-conflict detection, large-file guard, debug-statement detection, ruff lint+format, local mypy and pytest hooks.
- **`.mcp.json`** — Project-level MCP server configuration for Claude Code, wiring `copilot-memory`, `skills-copilot`, `task-copilot`, and `codekg` servers.
- **`CLAUDE.md`** — Project instructions for Claude Code with "Agent Identity" section, agent roster, session management, and project-specific rules.
- **`.claude/agents/`** — Thirteen specialized Claude agent configurations: `cco`, `cw`, `do`, `doc`, `kc`, `me`, `qa`, `sd`, `sec`, `ta`, `uid`, `uids`, `uxd`.
- **`.claude/commands/`** — Custom Claude command definitions: `changelog-commit`, `continue`, `protocol`, `setup-mcp`.
- **`docs/Architecture.md`** — Comprehensive architecture document covering design principles, data model, build pipeline, hybrid query model, ranking, snippet packing, call-site extraction, MCP layer, and deployment topology.
- **`docs/MCP.md`** — MCP server reference documentation covering tool signatures, usage examples, and client configuration.
- **`docs/deployment.md`** — Deployment guide covering local, Docker, and Claude Desktop/Code integration.
- **`docs/docker.md`** — Docker setup and usage guide.
- **`docs/logo.png`** — Project logo added to repository and displayed in README.
- **`docker/Dockerfile`** + **`docker/docker-compose.yml`** — Containerized deployment for the Streamlit visualizer app.
- **`.vscode/extensions.json`** — Recommended VSCode extensions for the project.

### Changed

- **`src/code_kg/kg.py`**, **`src/code_kg/mcp_server.py`** — `pack_snippets` defaults tightened: `max_lines` reduced from 160 → 60 and `max_nodes` from 50 → 15, keeping snippet packs concise and token-efficient by default.
- **`app.py` → `src/code_kg/app.py`** — Moved Streamlit visualizer into the package so it is bundled in the wheel and accessible after `pip install`. Major enhancements: interactive pyvis graph with gold-bordered seed nodes, rich tooltips, floating detail panel, tabbed UI (Graph / Query / Snippets). Default port changed from 8501 to 8500.
- **`scripts/install-skill.sh`** — Full rewrite into an AI integration layer installer. Replaced `CODEKG_BIN`/`_POETRY_RUN` with `PYTHON_BIN` detection (`.venv/bin/python` → `python3` on PATH → `pip install`). Build commands use `"${PYTHON_BIN}" -m code_kg`. MCP configs written with absolute python path and `-m code_kg mcp` args. Added `--providers` flag (`claude`, `kilo`, `copilot`, `cline`, `all`), `--dry-run`, and `--wipe` flags. `LANCEDB_DIR` unconditionally set to `.codekg/lancedb`; removed legacy path detection.
- **`.codekg/` unified artifact directory** — All generated files (SQLite graph and LanceDB vector index) now live under `.codekg/` (`graph.sqlite`, `lancedb/`). Updated across all CLI tools, the MCP server, `.mcp.json`, skills docs, command definitions, `.gitignore`, and all documentation.
- **CLI defaults (zero-config)** — `--repo`, `--db`, `--lancedb`, and `--repo-root` args on all CLI entry points are no longer required; they default to `.` / `.codekg/graph.sqlite` / `.codekg/lancedb`.
- **`__init__.py`** — Public API overhauled to expose `CodeGraph`, `GraphStore`, `SemanticIndex`, `CodeKG`, and all result types as top-level imports; low-level `Node`/`Edge` primitives retained under the locked v0 contract.
- **`tests/test_kg.py`** — Extended with 341 lines of new tests: `_compute_span`, `_read_lines`, `Snippet.to_dict()`, `QueryResult.print_summary()`, `SnippetPack.to_markdown()`, and `CodeKG` lazy-property and pipeline-method tests with mocked `SemanticIndex`.
- **`pyproject.toml`** — Development status upgraded from `3 - Alpha` to `4 - Beta`; added MCP and Docker-related dependencies.
- **`README.md`** — Completely rewritten with full project overview, MCP server documentation, Docker deployment, Claude Code integration guide, and `python -m code_kg` as the primary CLI invocation.
- **`docs/Architecture.md`**, **`docs/MCP.md`**, **`docs/deployment.md`** — All CLI examples and artifact references updated to `.codekg/` paths; MCP layer architecture and deployment topology expanded.
- **`.github/workflows/ci.yml`** — Simplified test matrix to Python 3.12 only; coverage upload unconditional.
- **`.vscode/mcp.json`** — Updated CodeKG MCP server args to use `.codekg/graph.sqlite` and `.codekg/lancedb`.
- **`tests/test_codekg_v0.py`** — Renamed to `tests/test_primitives.py` to reflect its scope.
- **`__version__`** — Bumped to `0.2.0`.

### Removed

- **`codekg_sqlite.py`** — Replaced by `src/code_kg/store.py` (`GraphStore`).
- **`codekg_lancedb.py`** — Replaced by `src/code_kg/index.py` (`SemanticIndex`).
- **`.streamlit/config.toml`** — Streamlit server configuration no longer bundled; app is part of the installed package.
- **`pyproject.old.toml`** — Stale backup removed.
- **`docs/code_kg.synctex.gz`** — Generated LaTeX artifact removed from version control.

### Fixed

- **`src/code_kg/index.py`** — Fixed LanceDB table-existence check: replaced deprecated `db.table_names()` with `db.list_tables().tables`; added fallback (`or 384`) for `get_sentence_embedding_dimension()` which can return `None`.
- **`src/code_kg/app.py`** — vis-network 9.x+ renders string `title` values as plain text; added `fixHtmlTitles()` to replace HTML string titles with DOM elements so rich tooltips render correctly.
- **`src/code_kg/codekg.py`** — Tightened `enclosing_def`/`owner_id` type annotations; simplified `dst_id` assignment.
- **`src/code_kg/kg.py`** — Replaced `file_cache.get()` + re-assign pattern with `if mp not in file_cache` for correct cache population.

---

## [0.1.0] - 2026-02-21

Initial release. See [release notes](release-notes.md) for full details.
