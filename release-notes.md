# Release Notes — v0.3.1

> Released: 2026-02-24

### Added

- **`codekg-analyze` CLI entry point** (`pyproject.toml`) — New Poetry script exposing `codekg_thorough_analysis:cli` as the `codekg-analyze` command. Runs a comprehensive structural and semantic analysis of a CodeKG knowledge graph and saves results to `~/.claude/codekg_analysis_latest.json`.
- **`cli()` entry point** (`codekg_thorough_analysis.py`) — Zero-argument wrapper around `main()` that parses `sys.argv` for `<repo_root>`, `<db_path>`, and `<lancedb_path>`, enabling the module to be registered as a Poetry script entry point. `__main__` block updated to call `cli()`.
- **`README.md` — CLI Usage section 7** — Documents `codekg-analyze` usage, arguments, and output location.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
