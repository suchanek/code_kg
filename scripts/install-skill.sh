#!/usr/bin/env bash
# =============================================================================
# install-skill.sh — Bootstrap the CodeKG skill on a new machine
#
# Installs to:
#   ~/.claude/skills/codekg/    (Claude Code — ~/.claude/commands/ for slash cmds)
#   ~/.kilocode/skills/codekg/  (Kilo Code — ~/.kilocode/skills/ for agent skills)
#   ~/.agents/skills/codekg/    (other agents)
#
# Also configures the target repo (defaults to CWD) end-to-end:
#   - Installs .claude/commands/codekg.md (Cline /codekg slash command)
#   - Installs code-kg via Poetry if not already present
#   - Builds the SQLite knowledge graph if not already present
#   - Builds the LanceDB vector index if not already present
#   - Writes .mcp.json (Kilo Code / Claude Code)
#   - Writes .vscode/mcp.json (GitHub Copilot)
#
# Usage (from the code_kg repo root):
#   bash scripts/install-skill.sh
#
# Usage (from a target repo, one-liner, no clone needed):
#   curl -fsSL https://raw.githubusercontent.com/suchanek/code_kg/main/scripts/install-skill.sh | bash
#
# What it does:
#   1. Creates skill directories for Claude Code, Kilo Code, and other agents
#   2. Downloads SKILL.md and references/installation.md from GitHub
#      (or copies from local repo if running from within the clone)
#   3. Installs .claude/commands/codekg.md into TARGET_REPO (Cline /codekg slash command)
#   4. Installs code-kg[mcp] via Poetry if codekg-mcp is not found
#   5. Builds the SQLite knowledge graph if codekg.sqlite does not exist
#   6. Builds the LanceDB vector index if the lancedb/ directory does not exist
#   7. Writes .mcp.json (Kilo Code / Claude Code per-repo config)
#   8. Writes .vscode/mcp.json (GitHub Copilot per-repo config)
#   9. Prints a final summary (only manual step: reload VS Code)
# =============================================================================

set -eo pipefail

REPO="suchanek/code_kg"
BRANCH="main"
RAW_BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"

# Install to Claude Code, Kilo Code, and other agent skill directories
SKILL_DIRS=(
    "${HOME}/.claude/skills/codekg"
    "${HOME}/.kilocode/skills/codekg"
    "${HOME}/.agents/skills/codekg"
)

# ── Detect if we're running from inside the repo ─────────────────────────────
# BASH_SOURCE[0] is unbound when piped via curl | bash.
# Use ${BASH_SOURCE:-} (no array index) which is safe even when unset.
_BASH_SOURCE="${BASH_SOURCE:-}"
if [ -n "$_BASH_SOURCE" ] && [ "$_BASH_SOURCE" != "bash" ]; then
    SCRIPT_DIR="$(cd "$(dirname "$_BASH_SOURCE")" && pwd)"
    REPO_ROOT="$(dirname "$SCRIPT_DIR")"
else
    # Running via curl | bash — no local clone available
    SCRIPT_DIR=""
    REPO_ROOT=""
fi
LOCAL_SKILL="${REPO_ROOT:+${REPO_ROOT}/.claude/skills/codekg/SKILL.md}"

# The target repo is where the user ran the script from (CWD).
TARGET_REPO="${PWD}"
SQLITE_DB="${TARGET_REPO}/codekg.sqlite"
# Prefer codekg_lancedb; fall back to lancedb for older installs
if [ -d "${TARGET_REPO}/codekg_lancedb" ]; then
    LANCEDB_DIR="${TARGET_REPO}/codekg_lancedb"
elif [ -d "${TARGET_REPO}/lancedb" ]; then
    LANCEDB_DIR="${TARGET_REPO}/lancedb"
else
    LANCEDB_DIR="${TARGET_REPO}/codekg_lancedb"
fi

echo "╔══════════════════════════════════════════════════╗"
echo "║       CodeKG Skill Installer                     ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Target repo: ${TARGET_REPO}"
echo ""

# ── Step 1: Install skill files to agent directories ─────────────────────────
echo "── Step 1: Installing skill files ──────────────────"
echo ""

for SKILL_DIR in "${SKILL_DIRS[@]}"; do
    REFS_DIR="${SKILL_DIR}/references"
    mkdir -p "$SKILL_DIR"
    mkdir -p "$REFS_DIR"

    if [ -f "$LOCAL_SKILL" ]; then
        if [ "${FIRST_RUN:-1}" = "1" ]; then
            echo "→ Local repo detected at: $REPO_ROOT"
            echo "  Copying skill files from local clone..."
            FIRST_RUN=0
        fi
        cp "${REPO_ROOT}/.claude/skills/codekg/SKILL.md" "${SKILL_DIR}/SKILL.md"
        cp "${REPO_ROOT}/.claude/skills/codekg/references/installation.md" "${REFS_DIR}/installation.md"
    else
        if [ "${FIRST_RUN:-1}" = "1" ]; then
            echo "→ No local clone detected. Downloading from GitHub..."
            FIRST_RUN=0
        fi
        if command -v curl &>/dev/null; then
            curl -fsSL "${RAW_BASE}/.claude/skills/codekg/SKILL.md" -o "${SKILL_DIR}/SKILL.md"
            curl -fsSL "${RAW_BASE}/.claude/skills/codekg/references/installation.md" -o "${REFS_DIR}/installation.md"
        elif command -v wget &>/dev/null; then
            wget -q "${RAW_BASE}/.claude/skills/codekg/SKILL.md" -O "${SKILL_DIR}/SKILL.md"
            wget -q "${RAW_BASE}/.claude/skills/codekg/references/installation.md" -O "${REFS_DIR}/installation.md"
        else
            echo "ERROR: Neither curl nor wget found. Install one and retry."
            exit 1
        fi
    fi

    # Verify
    if [ ! -f "${SKILL_DIR}/SKILL.md" ] || [ ! -f "${REFS_DIR}/installation.md" ]; then
        echo "ERROR: Installation failed for ${SKILL_DIR}"
        exit 1
    fi

    echo "  ✓ ${SKILL_DIR}/SKILL.md"
    echo "  ✓ ${REFS_DIR}/installation.md"
done

# ── Step 2: Install Cline slash command into the target repo ──────────────────
echo ""
echo "── Step 2: Installing Cline slash command ───────────"
echo ""

CLINE_CMD_DIR="${TARGET_REPO}/.claude/commands"
CLINE_CMD_FILE="${CLINE_CMD_DIR}/codekg.md"
LOCAL_CMD="${REPO_ROOT:+${REPO_ROOT}/.claude/commands/codekg.md}"

mkdir -p "$CLINE_CMD_DIR"

if [ -f "$CLINE_CMD_FILE" ]; then
    echo "  ✓ ${CLINE_CMD_FILE} already exists — skipping"
elif [ -n "$LOCAL_CMD" ] && [ -f "$LOCAL_CMD" ]; then
    cp "$LOCAL_CMD" "$CLINE_CMD_FILE"
    echo "  ✓ Copied from local repo → ${CLINE_CMD_FILE}"
else
    # Download from GitHub
    if command -v curl &>/dev/null; then
        curl -fsSL "${RAW_BASE}/.claude/commands/codekg.md" -o "$CLINE_CMD_FILE"
    elif command -v wget &>/dev/null; then
        wget -q "${RAW_BASE}/.claude/commands/codekg.md" -O "$CLINE_CMD_FILE"
    else
        echo "  ⚠ Neither curl nor wget found — skipping Cline command install"
    fi
    [ -f "$CLINE_CMD_FILE" ] && echo "  ✓ Downloaded → ${CLINE_CMD_FILE}"
fi

# ── Step 3: Install code-kg via Poetry if not already present ─────────────────
echo ""
echo "── Step 3: Checking code-kg installation ────────────"
echo ""

# Resolve absolute path to poetry — VS Code extension host doesn't inherit the
# user's shell PATH, so check common install locations explicitly.
_discover_poetry() {
    command -v poetry 2>/dev/null && return
    for _p in \
        "${HOME}/.local/bin/poetry" \
        "${HOME}/.poetry/bin/poetry" \
        "${HOME}/.pyenv/shims/poetry" \
        "/usr/local/bin/poetry" \
        "/opt/homebrew/bin/poetry"; do
        [ -x "$_p" ] && echo "$_p" && return
    done
}
POETRY_BIN="$(_discover_poetry || true)"

CODEKG_BIN=""
if [ -x "${TARGET_REPO}/.venv/bin/codekg-mcp" ]; then
    CODEKG_BIN="${TARGET_REPO}/.venv/bin/codekg-mcp"
    echo "  ✓ Found codekg-mcp in .venv: ${CODEKG_BIN}"
elif command -v codekg-mcp &>/dev/null; then
    CODEKG_BIN="$(command -v codekg-mcp)"
    echo "  ✓ Found codekg-mcp on PATH: ${CODEKG_BIN}"
elif command -v poetry &>/dev/null && (cd "${TARGET_REPO}" && poetry run codekg-mcp --help &>/dev/null 2>&1); then
    CODEKG_BIN="$(cd "${TARGET_REPO}" && poetry run which codekg-mcp 2>/dev/null || true)"
    echo "  ✓ Found codekg-mcp in poetry venv: ${CODEKG_BIN}"
fi

if [ -z "$CODEKG_BIN" ]; then
    if command -v poetry &>/dev/null; then
        echo "  → codekg-mcp not found. Installing code-kg[mcp] via Poetry..."
        (cd "${TARGET_REPO}" && poetry add 'code-kg[mcp] @ git+https://github.com/suchanek/code_kg.git')
        CODEKG_BIN="$(cd "${TARGET_REPO}" && poetry run which codekg-mcp 2>/dev/null || true)"
        if [ -n "$CODEKG_BIN" ]; then
            echo "  ✓ Installed code-kg — codekg-mcp at: ${CODEKG_BIN}"
        else
            echo "  ✗ Installation failed. Please install manually:"
            echo '      poetry add "code-kg[mcp] @ git+https://github.com/suchanek/code_kg.git"'
            echo "  Then re-run this script."
            exit 1
        fi
    else
        echo "  ✗ Neither codekg-mcp nor poetry found."
        echo "    Install Poetry first: https://python-poetry.org/docs/#installation"
        echo "    Then re-run this script."
        exit 1
    fi
fi

# From here on, use `poetry run codekg-*` for build commands (works regardless
# of whether CODEKG_BIN is an absolute path or resolved via poetry).
_POETRY_RUN=""
if command -v poetry &>/dev/null; then
    _POETRY_RUN="poetry run"
fi

# ── Step 4: Build the SQLite knowledge graph ──────────────────────────────────
echo ""
echo "── Step 4: Building SQLite knowledge graph ──────────"
echo ""

if [ -f "$SQLITE_DB" ]; then
    echo "  ✓ SQLite graph already exists: ${SQLITE_DB} — skipping build"
    echo "    (Run with --wipe to force rebuild)"
else
    echo "  → Building SQLite graph at: ${SQLITE_DB}"
    (cd "${TARGET_REPO}" && ${_POETRY_RUN} codekg-build-sqlite --repo "${TARGET_REPO}" --db "${SQLITE_DB}")
    if [ -f "$SQLITE_DB" ]; then
        NODE_COUNT=$(sqlite3 "$SQLITE_DB" "SELECT COUNT(*) FROM nodes;" 2>/dev/null || echo "?")
        EDGE_COUNT=$(sqlite3 "$SQLITE_DB" "SELECT COUNT(*) FROM edges;" 2>/dev/null || echo "?")
        echo "  ✓ Built: ${SQLITE_DB} (${NODE_COUNT} nodes, ${EDGE_COUNT} edges)"
    else
        echo "  ✗ Build failed — ${SQLITE_DB} not created"
        exit 1
    fi
fi

# ── Step 5: Build the LanceDB vector index ────────────────────────────────────
echo ""
echo "── Step 5: Building LanceDB vector index ────────────"
echo ""

if [ -d "$LANCEDB_DIR" ] && [ "$(ls -A "$LANCEDB_DIR" 2>/dev/null)" ]; then
    echo "  ✓ LanceDB index already exists: ${LANCEDB_DIR} — skipping build"
    echo "    (Run with --wipe to force rebuild)"
else
    echo "  → Building LanceDB index at: ${LANCEDB_DIR}"
    (cd "${TARGET_REPO}" && ${_POETRY_RUN} codekg-build-lancedb --sqlite "${SQLITE_DB}" --lancedb "${LANCEDB_DIR}")
    if [ -d "$LANCEDB_DIR" ] && [ "$(ls -A "$LANCEDB_DIR" 2>/dev/null)" ]; then
        echo "  ✓ Built: ${LANCEDB_DIR}"
    else
        echo "  ✗ Build failed — ${LANCEDB_DIR} not populated"
        exit 1
    fi
fi

# ── Step 6: Write .mcp.json (Kilo Code / Claude Code) ────────────────────────
echo ""
echo "── Step 6: Configuring .mcp.json (Kilo Code / Claude Code) ──"
echo ""

MCP_JSON="${TARGET_REPO}/.mcp.json"

if [ ! -f "$MCP_JSON" ]; then
    cat > "$MCP_JSON" <<EOF
{
  "mcpServers": {
    "codekg": {
      "command": "${CODEKG_BIN}",
      "args": [
        "--repo",
        "${TARGET_REPO}",
        "--db",
        "${SQLITE_DB}",
        "--lancedb",
        "${LANCEDB_DIR}"
      ]
    }
  }
}
EOF
    echo "  ✓ Created ${MCP_JSON}"
elif grep -q '"codekg"' "$MCP_JSON"; then
    echo "  ✓ codekg entry already present in ${MCP_JSON} — skipping"
else
    python3 - "$MCP_JSON" "$TARGET_REPO" "$SQLITE_DB" "$LANCEDB_DIR" "$CODEKG_BIN" <<'PYEOF'
import json, sys
mcp_json_path = sys.argv[1]
target_repo   = sys.argv[2]
sqlite_db     = sys.argv[3]
lancedb_dir   = sys.argv[4]
codekg_bin    = sys.argv[5]
with open(mcp_json_path, "r") as f:
    data = json.load(f)
if "mcpServers" not in data:
    data["mcpServers"] = {}
data["mcpServers"]["codekg"] = {
    "command": codekg_bin,
    "args": ["--repo", target_repo, "--db", sqlite_db, "--lancedb", lancedb_dir]
}
with open(mcp_json_path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF
    echo "  ✓ Added codekg entry to ${MCP_JSON}"
fi

# ── Step 7: Write .vscode/mcp.json (GitHub Copilot) ──────────────────────────
echo ""
echo "── Step 7: Configuring .vscode/mcp.json (GitHub Copilot) ──"
echo ""

VSCODE_DIR="${TARGET_REPO}/.vscode"
VSCODE_MCP="${VSCODE_DIR}/mcp.json"
mkdir -p "$VSCODE_DIR"

if [ ! -f "$VSCODE_MCP" ]; then
    cat > "$VSCODE_MCP" <<EOF
{
  "servers": {
    "codekg": {
      "type": "stdio",
      "command": "${CODEKG_BIN}",
      "args": [
        "--repo",
        "${TARGET_REPO}",
        "--db",
        "${SQLITE_DB}",
        "--lancedb",
        "${LANCEDB_DIR}"
      ]
    }
  }
}
EOF
    echo "  ✓ Created ${VSCODE_MCP}"
elif grep -q '"codekg"' "$VSCODE_MCP"; then
    echo "  ✓ codekg entry already present in ${VSCODE_MCP} — skipping"
else
    python3 - "$VSCODE_MCP" "$TARGET_REPO" "$SQLITE_DB" "$LANCEDB_DIR" "$CODEKG_BIN" <<'PYEOF'
import json, sys
vscode_mcp  = sys.argv[1]
target_repo = sys.argv[2]
sqlite_db   = sys.argv[3]
lancedb_dir = sys.argv[4]
codekg_bin  = sys.argv[5]
with open(vscode_mcp, "r") as f:
    data = json.load(f)
if "servers" not in data:
    data["servers"] = {}
data["servers"]["codekg"] = {
    "type": "stdio",
    "command": codekg_bin,
    "args": ["--repo", target_repo, "--db", sqlite_db, "--lancedb", lancedb_dir]
}
with open(vscode_mcp, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF
    echo "  ✓ Added codekg entry to ${VSCODE_MCP}"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   CodeKG installed and configured successfully!  ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Repo:    ${TARGET_REPO}"
echo "  SQLite:  ${SQLITE_DB}"
echo "  LanceDB: ${LANCEDB_DIR}"
echo "  .mcp.json:        configured (Kilo Code / Claude Code)"
echo "  .vscode/mcp.json: configured (GitHub Copilot)"
echo "  /codekg slash cmd: installed (Cline)"
echo ""
echo "  ⚠ One manual step required:"
echo "    Reload VS Code to activate the MCP servers:"
echo "    Cmd+Shift+P → 'Developer: Reload Window'"
echo ""
echo "  GitHub Copilot: VS Code will prompt you to Trust the codekg server"
echo "  on first use after reload."
echo ""
echo "  Full docs: https://github.com/suchanek/code_kg/blob/main/docs/MCP.md"
