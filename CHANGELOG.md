# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
