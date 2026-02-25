# Release Notes — v0.3.2

> Released: 2026-02-25

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

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
