#!/usr/bin/env bash
# =============================================================================
# install-skill.sh — Bootstrap the CodeKG AI integration layer
#
# Installs SKILL.md reference files and the /codekg slash command for AI agents,
# then configures MCP server integration for the specified providers.
#
# Supported providers:
#   claude   — Claude Code  (.mcp.json)
#   kilo     — Kilo Code    (.mcp.json, shared with Claude Code)
#   copilot  — GitHub Copilot (.vscode/mcp.json)
#   cline    — Cline        (.claude/commands/codekg.md slash command)
#
# Usage (from a target repo, no clone needed):
#   curl -fsSL https://raw.githubusercontent.com/suchanek/code_kg/main/scripts/install-skill.sh | bash
#
# With provider selection:
#   curl -fsSL .../install-skill.sh | bash -s -- --providers all
#   curl -fsSL .../install-skill.sh | bash -s -- --providers claude,copilot
#   bash scripts/install-skill.sh --providers kilo,cline
#
# Flags:
#   --providers <list>   Comma-separated provider names, or "all" (default: all)
#   --wipe               Force rebuild of SQLite graph and LanceDB index
#   --dry-run            Print what would be done without making any changes
#
# What it does:
#   1. Creates skill directories for Claude Code, Kilo Code, and other agents
#   2. Downloads SKILL.md and references/installation.md from GitHub
#      (or copies from local repo if running from within the clone)
#   3. Installs code-kg[mcp] if codekg-mcp is not found:
#        a. pip install from latest GitHub release wheel (preferred, no git needed)
#        b. pip install from git+https (fallback, needs git)
#        c. poetry add (fallback for Poetry-managed repos)
#   4. Builds the SQLite knowledge graph (skips if already present, unless --wipe)
#   5. Builds the LanceDB vector index  (skips if already present, unless --wipe)
#   6. Writes provider MCP configs as requested
#   7. Prints a final summary
# =============================================================================

set -eo pipefail

# ── Parse arguments ───────────────────────────────────────────────────────────
PROVIDERS_ARG="all"
WIPE_FLAG=""
DRY_RUN=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --providers)
            PROVIDERS_ARG="${2:-all}"
            shift 2
            ;;
        --providers=*)
            PROVIDERS_ARG="${1#*=}"
            shift
            ;;
        --wipe)
            WIPE_FLAG="1"
            shift
            ;;
        --dry-run)
            DRY_RUN="1"
            shift
            ;;
        *)
            echo "Unknown flag: $1"
            echo "Usage: $0 [--providers all|claude,kilo,copilot,cline] [--wipe] [--dry-run]"
            exit 1
            ;;
    esac
done

# Run a command, or in dry-run mode just print what would be executed.
_exec() {
    if [ -n "$DRY_RUN" ]; then
        echo "  [dry-run] $*"
    else
        "$@"
    fi
}

# Normalise to a set of boolean flags
DO_CLAUDE=0; DO_KILO=0; DO_COPILOT=0; DO_CLINE=0

_enable_provider() {
    case "$1" in
        all)    DO_CLAUDE=1; DO_KILO=1; DO_COPILOT=1; DO_CLINE=1 ;;
        claude) DO_CLAUDE=1 ;;
        kilo)   DO_KILO=1 ;;
        copilot)DO_COPILOT=1 ;;
        cline)  DO_CLINE=1 ;;
        *)
            echo "Unknown provider: $1  (valid: all, claude, kilo, copilot, cline)"
            exit 1
            ;;
    esac
}

IFS=',' read -ra _PLIST <<< "$PROVIDERS_ARG"
for _p in "${_PLIST[@]}"; do
    _enable_provider "$(echo "$_p" | tr -d ' ')"
done

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
echo "║       CodeKG Integration Installer               ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
[ -n "$DRY_RUN" ] && echo "  *** DRY RUN — no changes will be made ***"
echo "  Target repo: ${TARGET_REPO}"
_PNAMES=""
[ "$DO_CLAUDE"  = "1" ] && _PNAMES="${_PNAMES} claude"
[ "$DO_KILO"    = "1" ] && _PNAMES="${_PNAMES} kilo"
[ "$DO_COPILOT" = "1" ] && _PNAMES="${_PNAMES} copilot"
[ "$DO_CLINE"   = "1" ] && _PNAMES="${_PNAMES} cline"
echo "  Providers:   ${_PNAMES# }"
echo ""

# ── Step 1: Install skill files to agent directories ─────────────────────────
echo "── Step 1: Installing skill files ──────────────────"
echo ""

for SKILL_DIR in "${SKILL_DIRS[@]}"; do
    REFS_DIR="${SKILL_DIR}/references"
    _exec mkdir -p "$SKILL_DIR"
    _exec mkdir -p "$REFS_DIR"

    if [ -f "$LOCAL_SKILL" ]; then
        if [ "${FIRST_RUN:-1}" = "1" ]; then
            echo "→ Local repo detected at: $REPO_ROOT"
            echo "  Copying skill files from local clone..."
            FIRST_RUN=0
        fi
        _exec cp "${REPO_ROOT}/.claude/skills/codekg/SKILL.md" "${SKILL_DIR}/SKILL.md"
        _exec cp "${REPO_ROOT}/.claude/skills/codekg/references/installation.md" "${REFS_DIR}/installation.md"
    else
        if [ "${FIRST_RUN:-1}" = "1" ]; then
            echo "→ No local clone detected. Downloading from GitHub..."
            FIRST_RUN=0
        fi
        if [ -n "$DRY_RUN" ]; then
            echo "  [dry-run] would download ${RAW_BASE}/.claude/skills/codekg/SKILL.md → ${SKILL_DIR}/SKILL.md"
            echo "  [dry-run] would download ${RAW_BASE}/.claude/skills/codekg/references/installation.md → ${REFS_DIR}/installation.md"
        elif command -v curl &>/dev/null; then
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

    # Verify (skip in dry-run — files may not exist yet)
    if [ -z "$DRY_RUN" ]; then
        if [ ! -f "${SKILL_DIR}/SKILL.md" ] || [ ! -f "${REFS_DIR}/installation.md" ]; then
            echo "ERROR: Installation failed for ${SKILL_DIR}"
            exit 1
        fi
    fi

    echo "  ✓ ${SKILL_DIR}/SKILL.md"
    echo "  ✓ ${REFS_DIR}/installation.md"
done

# ── Step 2: Install Cline slash command into the target repo ──────────────────
echo ""
echo "── Step 2: Installing Cline slash command ───────────"
echo ""

if [ "$DO_CLINE" = "1" ]; then
    CLINE_CMD_DIR="${TARGET_REPO}/.claude/commands"
    CLINE_CMD_FILE="${CLINE_CMD_DIR}/codekg.md"
    LOCAL_CMD="${REPO_ROOT:+${REPO_ROOT}/.claude/commands/codekg.md}"

    _exec mkdir -p "$CLINE_CMD_DIR"

    if [ -f "$CLINE_CMD_FILE" ]; then
        echo "  ✓ ${CLINE_CMD_FILE} already exists — skipping"
    elif [ -n "$LOCAL_CMD" ] && [ -f "$LOCAL_CMD" ]; then
        _exec cp "$LOCAL_CMD" "$CLINE_CMD_FILE"
        echo "  ✓ Copied from local repo → ${CLINE_CMD_FILE}"
    else
        # Download from GitHub
        if [ -n "$DRY_RUN" ]; then
            echo "  [dry-run] would download ${RAW_BASE}/.claude/commands/codekg.md → ${CLINE_CMD_FILE}"
        elif command -v curl &>/dev/null; then
            curl -fsSL "${RAW_BASE}/.claude/commands/codekg.md" -o "$CLINE_CMD_FILE"
            echo "  ✓ Downloaded → ${CLINE_CMD_FILE}"
        elif command -v wget &>/dev/null; then
            wget -q "${RAW_BASE}/.claude/commands/codekg.md" -O "$CLINE_CMD_FILE"
            echo "  ✓ Downloaded → ${CLINE_CMD_FILE}"
        else
            echo "  ⚠ Neither curl nor wget found — skipping Cline command install"
        fi
    fi
else
    echo "  – Skipped (cline not selected)"
fi

# ── Step 3: Install code-kg if not already present ────────────────────────────
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

# Resolve the latest GitHub release wheel URL (requires curl or wget + python3).
# Returns empty string if no release exists yet.
_latest_wheel_url() {
    local _api="https://api.github.com/repos/${REPO}/releases/latest"
    local _json=""
    if command -v curl &>/dev/null; then
        _json="$(curl -fsSL "$_api" 2>/dev/null || true)"
    elif command -v wget &>/dev/null; then
        _json="$(wget -qO- "$_api" 2>/dev/null || true)"
    fi
    [ -z "$_json" ] && return
    python3 - <<PYEOF
import json, sys
try:
    data = json.loads('''$_json''')
    assets = data.get("assets", [])
    whl = next((a["browser_download_url"] for a in assets if a["name"].endswith(".whl")), None)
    if whl:
        print(whl)
except Exception:
    pass
PYEOF
}

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
    if [ -n "$DRY_RUN" ]; then
        echo "  [dry-run] would install code-kg[mcp] (wheel from GitHub Releases or git fallback)"
        CODEKG_BIN="<venv>/bin/codekg-mcp"
    else
        # ── Preferred: install from latest GitHub release wheel (no git needed) ──
        WHEEL_URL="$(_latest_wheel_url || true)"
        if [ -n "$WHEEL_URL" ]; then
            echo "  → Installing code-kg[mcp] from GitHub release wheel..."
            pip install --quiet "code-kg[mcp] @ ${WHEEL_URL}"
        else
            # ── Fallback 1: pip from git (always works, needs git) ────────────
            echo "  → No release found. Installing code-kg[mcp] from git..."
            pip install --quiet "code-kg[mcp] @ git+https://github.com/${REPO}.git"
        fi
        CODEKG_BIN="$(command -v codekg-mcp 2>/dev/null || true)"

        # ── Fallback 2: poetry add (for Poetry-managed target repos) ─────────
        if [ -z "$CODEKG_BIN" ] && command -v poetry &>/dev/null; then
            echo "  → pip install did not land codekg-mcp on PATH; trying poetry add..."
            if [ -n "$WHEEL_URL" ]; then
                (cd "${TARGET_REPO}" && poetry add "code-kg[mcp] @ ${WHEEL_URL}")
            else
                (cd "${TARGET_REPO}" && poetry add "code-kg[mcp] @ git+https://github.com/${REPO}.git")
            fi
            CODEKG_BIN="$(cd "${TARGET_REPO}" && poetry run which codekg-mcp 2>/dev/null || true)"
        fi

        if [ -n "$CODEKG_BIN" ]; then
            echo "  ✓ Installed code-kg — codekg-mcp at: ${CODEKG_BIN}"
        else
            echo "  ✗ Installation failed. Install manually:"
            echo "      pip install 'code-kg[mcp] @ git+https://github.com/${REPO}.git'"
            exit 1
        fi
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

if [ -f "$SQLITE_DB" ] && [ -z "$WIPE_FLAG" ]; then
    echo "  ✓ SQLite graph already exists: ${SQLITE_DB} — skipping build"
    echo "    (Run with --wipe to force rebuild)"
else
    if [ -n "$WIPE_FLAG" ]; then
        _exec rm -f "$SQLITE_DB"
    fi
    if [ -n "$DRY_RUN" ]; then
        echo "  [dry-run] would run: codekg-build-sqlite --repo ${TARGET_REPO} --db ${SQLITE_DB}"
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
fi

# ── Step 5: Build the LanceDB vector index ────────────────────────────────────
echo ""
echo "── Step 5: Building LanceDB vector index ────────────"
echo ""

if [ -d "$LANCEDB_DIR" ] && [ "$(ls -A "$LANCEDB_DIR" 2>/dev/null)" ] && [ -z "$WIPE_FLAG" ]; then
    echo "  ✓ LanceDB index already exists: ${LANCEDB_DIR} — skipping build"
    echo "    (Run with --wipe to force rebuild)"
else
    if [ -n "$WIPE_FLAG" ]; then
        _exec rm -rf "$LANCEDB_DIR"
    fi
    if [ -n "$DRY_RUN" ]; then
        echo "  [dry-run] would run: codekg-build-lancedb --sqlite ${SQLITE_DB} --lancedb ${LANCEDB_DIR}"
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
fi

# ── Step 6: Write .mcp.json (Claude Code / Kilo Code) ────────────────────────
echo ""
echo "── Step 6: Configuring .mcp.json (Claude Code / Kilo Code) ──"
echo ""

MCP_JSON="${TARGET_REPO}/.mcp.json"

if [ "$DO_CLAUDE" = "0" ] && [ "$DO_KILO" = "0" ]; then
    echo "  – Skipped (neither claude nor kilo selected)"
elif [ -n "$DRY_RUN" ]; then
    if [ ! -f "$MCP_JSON" ]; then
        echo "  [dry-run] would create ${MCP_JSON}"
    elif grep -q '"codekg"' "$MCP_JSON"; then
        echo "  [dry-run] codekg entry already present in ${MCP_JSON} — no change needed"
    else
        echo "  [dry-run] would merge codekg entry into existing ${MCP_JSON}"
    fi
elif [ ! -f "$MCP_JSON" ]; then
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

if [ "$DO_COPILOT" = "0" ]; then
    echo "  – Skipped (copilot not selected)"
elif [ -n "$DRY_RUN" ]; then
    if [ ! -f "$VSCODE_MCP" ]; then
        echo "  [dry-run] would create ${VSCODE_MCP}"
    elif grep -q '"codekg"' "$VSCODE_MCP"; then
        echo "  [dry-run] codekg entry already present in ${VSCODE_MCP} — no change needed"
    else
        echo "  [dry-run] would merge codekg entry into existing ${VSCODE_MCP}"
    fi
else
    _exec mkdir -p "$VSCODE_DIR"

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
fi  # DO_COPILOT

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
if [ -n "$DRY_RUN" ]; then
echo "╔══════════════════════════════════════════════════╗"
echo "║   CodeKG dry-run complete — no changes made.     ║"
echo "╚══════════════════════════════════════════════════╝"
else
echo "╔══════════════════════════════════════════════════╗"
echo "║   CodeKG installed and configured successfully!  ║"
echo "╚══════════════════════════════════════════════════╝"
fi
echo ""
echo "  Repo:    ${TARGET_REPO}"
echo "  SQLite:  ${SQLITE_DB}"
echo "  LanceDB: ${LANCEDB_DIR}"
echo ""
echo "  Providers configured:"
[ "$DO_CLAUDE"  = "1" ] && echo "    ✓ Claude Code    (.mcp.json)"
[ "$DO_KILO"    = "1" ] && echo "    ✓ Kilo Code      (.mcp.json)"
[ "$DO_COPILOT" = "1" ] && echo "    ✓ GitHub Copilot (.vscode/mcp.json)"
[ "$DO_CLINE"   = "1" ] && echo "    ✓ Cline          (.claude/commands/codekg.md)"
echo ""
echo "  ⚠ One manual step required:"
echo "    Reload VS Code to activate the MCP servers:"
echo "    Cmd+Shift+P → 'Developer: Reload Window'"
echo ""
[ "$DO_COPILOT" = "1" ] && echo "  GitHub Copilot: VS Code will prompt you to Trust the codekg server on first use."
echo ""
echo "  Full docs: https://github.com/suchanek/code_kg/blob/main/docs/MCP.md"
