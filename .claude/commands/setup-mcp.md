# CodeKG MCP Setup & Verification

Set up the CodeKG MCP server for a target repository and configure it for use with Claude Code and/or Claude Desktop. Execute the following steps in sequence.

## Command Argument Handling

This command accepts an optional repository path argument:

**Usage:**
- `/setup-mcp` — Interactive mode; prompts for the target repository path
- `/setup-mcp /path/to/repo` — Set up CodeKG MCP for the specified repository

---

## Step 0: Resolve the Target Repository

1. If a path argument was provided, use it as `REPO_ROOT`.
2. If no argument was provided, ask the user:
   > "Which repository do you want to index? Please provide the absolute path."
3. Verify the path exists and contains at least one `.py` file:
   ```bash
   find "$REPO_ROOT" -name "*.py" -not -path "*/.venv/*" -not -path "*/__pycache__/*" | head -5
   ```
4. If no Python files are found, stop and report the issue.

Derive artifact paths from `REPO_ROOT`:
- `DB_PATH` → `$REPO_ROOT/codekg.sqlite`
- `LANCEDB_DIR` → `$REPO_ROOT/lancedb`

---

## Step 1: Verify CodeKG Installation

The package is managed via Poetry, so all checks use `poetry run`.

1. Check that the `codekg-mcp` entry point is available in the venv:
   ```bash
   poetry run which codekg-mcp
   ```
2. If not found, check whether the package is installed:
   ```bash
   poetry show code-kg 2>/dev/null || pip show code-kg 2>/dev/null
   ```
3. If the package is missing, instruct the user to install it:
   ```bash
   poetry add "code-kg[mcp]"
   ```
   Then stop — the user must install before continuing.

4. If the package is installed but `codekg-mcp` is missing, the `mcp` extra is likely absent:
   ```bash
   poetry add mcp
   ```

5. Confirm the `mcp` Python package is importable:
   ```bash
   poetry run python -c "import mcp; print('mcp OK')"
   ```
   If this fails, report the error and stop.

---

## Step 2: Build the Knowledge Graph (SQLite)

1. Check whether `DB_PATH` already exists:
   ```bash
   ls -lh "$DB_PATH" 2>/dev/null
   ```
2. If it exists, ask the user:
   > "A knowledge graph already exists at `$DB_PATH`. Rebuild it from scratch (wipe), or keep the existing graph?"
   - **Wipe**: proceed with `--wipe`
   - **Keep**: skip to Step 3

3. Run the static analysis build:
   ```bash
   poetry run codekg-build-sqlite --repo "$REPO_ROOT" --db "$DB_PATH" --wipe
   ```
4. Verify the database was created and is non-empty:
   ```bash
   sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM nodes; SELECT COUNT(*) FROM edges;"
   ```
5. Report the node and edge counts. If both are zero, warn the user — the repo may have no indexable Python files.

---

## Step 3: Build the Semantic Index (LanceDB)

1. Check whether `LANCEDB_DIR` already exists and is non-empty:
   ```bash
   ls "$LANCEDB_DIR" 2>/dev/null
   ```
2. If it exists and the user chose to keep the SQLite graph (Step 2), ask:
   > "A vector index already exists at `$LANCEDB_DIR`. Rebuild it?"
   - **Yes**: proceed with `--wipe`
   - **No**: skip to Step 4

3. Run the embedding build:
   ```bash
   poetry run codekg-build-lancedb --sqlite "$DB_PATH" --lancedb "$LANCEDB_DIR" --wipe
   ```
4. Confirm the LanceDB directory was populated:
   ```bash
   ls -lh "$LANCEDB_DIR"
   ```
5. Report the number of indexed vectors (shown in the command output).

---

## Step 4: Smoke-Test the Query Pipeline

Run a quick end-to-end test to confirm the full pipeline works before configuring any agent:

1. Run a graph stats check:
   ```bash
   poetry run python -c "
   from code_kg import CodeKG
   kg = CodeKG(repo_root='$REPO_ROOT', db_path='$DB_PATH', lancedb_dir='$LANCEDB_DIR')
   import json; print(json.dumps(kg.stats(), indent=2))
   "
   ```

2. Run a sample query (note: flag is `--sqlite`, not `--db`):
   ```bash
   poetry run codekg-query --sqlite "$DB_PATH" --lancedb "$LANCEDB_DIR" --q "module structure"
   ```

3. If either command errors, diagnose and report the issue before proceeding.

---

## Step 5: Configure MCP Clients

Configure both Claude Code (`.mcp.json`) and Claude Desktop (`claude_desktop_config.json`) if applicable, and install the CodeKG skill globally.

### 5a: Claude Code (.mcp.json)

Claude Code reads MCP servers from `.mcp.json` in the project root. Use `poetry run` so the entry point resolves correctly regardless of venv path.

1. Check if `.mcp.json` exists in `$REPO_ROOT`:
   ```bash
   cat "$REPO_ROOT/.mcp.json" 2>/dev/null
   ```

2. If it exists, check for an existing `codekg` entry under `mcpServers`.
   - If one exists, ask the user to replace or keep it.

3. The `codekg` entry to add/update:
   ```json
   "codekg": {
     "command": "poetry",
     "args": [
       "run", "codekg-mcp",
       "--repo",    "<REPO_ROOT>",
       "--db",      "<DB_PATH>",
       "--lancedb", "<LANCEDB_DIR>"
     ]
   }
   ```

4. Merge into the existing `mcpServers` object — do not overwrite other entries.

### 5b: Claude Desktop (claude_desktop_config.json)

Claude Desktop does not have Poetry on its PATH, so use the absolute path to the venv binary.

1. Determine the config path:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Linux**: `~/.config/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

2. Get the venv binary path:
   ```bash
   poetry env info --path
   ```
   The binary is at `<venv_path>/bin/codekg-mcp`.

3. Check whether the config file exists and read it:
   ```bash
   cat "$CONFIG_PATH" 2>/dev/null
   ```

4. If a `codekg` entry already exists, ask the user to replace or keep it.

5. The `codekg` entry to add/update (use the absolute venv path):
   ```json
   "codekg": {
     "command": "<venv_path>/bin/codekg-mcp",
     "args": [
       "--repo",    "<REPO_ROOT>",
       "--db",      "<DB_PATH>",
       "--lancedb", "<LANCEDB_DIR>"
     ]
   }
   ```

6. Merge into the existing `mcpServers` object — do not overwrite other entries.

7. Show the user the final `codekg` block that was written.

### 5c: Install the CodeKG Skill (Global)

The CodeKG skill provides Claude with expert knowledge about CodeKG installation and usage. It lives in the `code_kg` repo and must be copied to `~/.claude/skills/` so the `skills-copilot` MCP server can serve it globally across all projects.

1. Locate the skill source in the `code_kg` repo. The repo is at the path where `code-kg` was installed from — find it:
   ```bash
   poetry run python -c "import code_kg; import pathlib; print(pathlib.Path(code_kg.__file__).parent.parent.parent)"
   ```
   This prints the repo root (e.g. `/Users/you/repos/code_kg` or the pip cache path).

   Alternatively, if the user cloned the repo, ask:
   > "Where is the code_kg repository cloned? (e.g. /Users/you/repos/code_kg)"

2. Check if the skill source exists:
   ```bash
   ls "<CODE_KG_REPO>/.claude/skills/codekg/SKILL.md" 2>/dev/null && echo "SKILL_SOURCE_OK" || echo "SKILL_SOURCE_MISSING"
   ```

3. Check if the skill is already installed globally:
   ```bash
   ls ~/.claude/skills/codekg/SKILL.md 2>/dev/null && echo "ALREADY_INSTALLED" || echo "NOT_INSTALLED"
   ```

4. If `ALREADY_INSTALLED`, ask the user:
   > "The codekg skill is already installed at `~/.claude/skills/codekg/`. Update it with the latest version from the repo?"
   - **Yes**: proceed with copy (overwrites)
   - **No**: skip to Step 6

5. Copy the skill to the global skills directory:
   ```bash
   mkdir -p ~/.claude/skills/codekg/references
   cp "<CODE_KG_REPO>/.claude/skills/codekg/SKILL.md" ~/.claude/skills/codekg/SKILL.md
   cp "<CODE_KG_REPO>/.claude/skills/codekg/references/installation.md" ~/.claude/skills/codekg/references/installation.md
   ```

6. Verify:
   ```bash
   ls -lh ~/.claude/skills/codekg/SKILL.md
   ls -lh ~/.claude/skills/codekg/references/installation.md
   ```

7. If `SKILL_SOURCE_MISSING` (e.g. installed from pip cache, not a local clone), skip this step and note in the final report that the skill must be installed manually by cloning the repo.

---

## Step 6: Final Report

Present a summary of everything that was done:

```
✓ Repository indexed:   <REPO_ROOT>
✓ SQLite graph:         <DB_PATH>  (<N> nodes, <M> edges)
✓ LanceDB index:        <LANCEDB_DIR>  (<V> vectors)
✓ Smoke test:           passed
✓ Claude Code config:   <REPO_ROOT>/.mcp.json
✓ Claude Desktop config: <CONFIG_PATH>
✓ CodeKG skill:         ~/.claude/skills/codekg/  (installed/updated/skipped)

Restart Claude Code / Claude Desktop to activate the codekg MCP server.

Available tools once active:
  • graph_stats()          — codebase size and shape
  • query_codebase(q)      — semantic + structural exploration
  • pack_snippets(q)       — source-grounded code snippets
  • get_node(node_id)      — single node metadata lookup

Suggested first query after restart:
  graph_stats()
```

---

## Important Rules

- **Do NOT modify source files** in the target repository.
- **Do NOT run `git commit`** or any destructive git operations.
- Use **absolute paths** everywhere — relative paths will break MCP clients.
- Always use `poetry run` for CLI calls — the package is not installed globally.
- If any step fails, stop and report the error clearly before proceeding.
- If the user's repo is very large (>50k lines of Python), warn that the build and embedding steps may take several minutes.

---

## Rebuilding After Code Changes

When the target codebase changes, the graph must be rebuilt. Remind the user:

```bash
# Rebuild both artifacts (idempotent — safe to re-run)
poetry run codekg-build-sqlite  --repo "$REPO_ROOT" --db "$DB_PATH" --wipe
poetry run codekg-build-lancedb --sqlite "$DB_PATH" --lancedb "$LANCEDB_DIR" --wipe
```

The MCP client configs do not need to change — they point to the same file paths.
