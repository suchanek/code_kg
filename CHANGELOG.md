# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
