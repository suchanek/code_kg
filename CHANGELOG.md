# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`src/code_kg/mcp_server.py`** — MCP server exposing `graph_stats`, `query_codebase`, `pack_snippets`, and `get_node` tools for AI agent integration via the Model Context Protocol.
- **`Dockerfile`** + **`docker-compose.yml`** — Containerized deployment for the Streamlit visualizer app with multi-stage build and volume mounts for SQLite/LanceDB artifacts.
- **`.dockerignore`** — Docker build exclusions.
- **`.streamlit/config.toml`** — Streamlit server configuration for containerized and local deployments.
- **`.mcp.json`** — Project-level MCP server configuration for Claude Code, wiring `copilot-memory`, `skills-copilot`, `task-copilot`, and `codekg` servers.
- **`CLAUDE.md`** — Project instructions for Claude Code with agent roster, session management, and project-specific rules.
- **`.claude/commands/setup-mcp.md`** — `/setup-mcp` command: end-to-end CodeKG MCP setup and verification workflow covering build, smoke-test, and client configuration for both Claude Code and Claude Desktop.
- **`docs/MCP.md`** — MCP server reference documentation covering tool signatures, usage examples, and client configuration.
- **`docs/deployment.md`** — Deployment guide covering local, Docker, and Claude Desktop/Code integration.
- **`docs/docker.md`** — Docker setup and usage guide.

### Changed

- **`app.py`** — Major Streamlit visualizer enhancements: interactive pyvis graph with gold-bordered seed nodes, rich tooltips, floating detail panel, tabbed UI (Graph / Query / Snippets), sidebar controls for repo/db path configuration and query parameters.
- **`README.md`** — Updated with MCP server documentation, Docker deployment instructions, and Claude Code integration guide.
- **`docs/Architecture.md`** — Expanded with MCP layer architecture, deployment topology, and client integration details.
- **`.claude/agents/*.md`** — Minor trailing-newline normalization across all thirteen agent files.
- **`pyproject.toml`** — Added MCP and Docker-related dependencies.

### Removed

- **`pyproject.old.toml`** — Stale backup removed.



- **`graph.py`** — `CodeGraph`: OOP wrapper around `extract_repo()` providing a cached, chainable interface to pure AST extraction with no side effects.
- **`store.py`** — `GraphStore`: SQLite persistence layer replacing the removed `codekg_sqlite.py`; exposes `write()`, `query_neighbors()`, and `provenance`-aware graph traversal via `ProvMeta`.
- **`index.py`** — `SemanticIndex` + pluggable `Embedder` abstraction replacing `codekg_lancedb.py`; includes `SentenceTransformerEmbedder` and `SeedHit` result type for typed semantic search results.
- **`kg.py`** — `CodeKG` top-level orchestrator owning the full pipeline (repo → `CodeGraph` → `GraphStore` → `SemanticIndex` → results); defines structured result types `BuildStats`, `QueryResult`, `Snippet`, and `SnippetPack`.
- **`docs/Architecture.md`** — Comprehensive architecture document covering design principles, data model, build pipeline, hybrid query model, ranking, snippet packing, and call-site extraction.
- **`.claude/agents/`** — Thirteen specialized Claude agent configurations: `cco`, `cw`, `do`, `doc`, `kc`, `me`, `qa`, `sd`, `sec`, `ta`, `uid`, `uids`, `uxd`.
- **`.claude/commands/`** — Three custom Claude command definitions: `changelog-commit`, `continue`, `protocol`.
- **`.vscode/extensions.json`** — Recommended VSCode extensions for the project.
- **`tests/test_graph.py`**, **`tests/test_kg.py`**, **`tests/test_store.py`** — Full unit test suites for the three new layered classes.

### Changed

- **`__init__.py`** — Public API overhauled to expose `CodeGraph`, `GraphStore`, `SemanticIndex`, `CodeKG`, and all result types as top-level imports; low-level `Node`/`Edge` primitives retained under the locked v0 contract.
- **`README.md`** — Completely rewritten with full project overview, motivation, design principles, data model reference, build pipeline description, hybrid query model, CLI usage, output artifacts table, and project structure.
- **`build_codekg_sqlite.py`**, **`build_codekg_lancedb.py`**, **`codekg_query.py`**, **`codekg_snippet_packer.py`** — Updated to integrate with the new layered class API.
- **`tests/test_codekg_v0.py`** — Renamed to `tests/test_primitives.py` to reflect its scope (v0 primitive contract tests).

### Removed

- **`codekg_sqlite.py`** — Replaced by `store.py` (`GraphStore`).
- **`codekg_lancedb.py`** — Replaced by `index.py` (`SemanticIndex`).
- **`docs/code_kg.synctex.gz`** — Generated LaTeX artifact removed from version control.
