#!/usr/bin/env bash
# =============================================================================
# install-skill.sh — Bootstrap the CodeKG skill on a new machine
#
# Installs to:
#   ~/.claude/skills/codekg/    (Claude Code — ~/.claude/commands/ for slash cmds)
#   ~/.kilocode/skills/codekg/  (Kilo Code — ~/.kilocode/skills/ for agent skills)
#   ~/.agents/skills/codekg/    (other agents)
#
# Also injects the codekg MCP server entry into .mcp.json in the TARGET_REPO
# (defaults to the current working directory when the script is run).
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
#   3. Injects the codekg MCP server entry into .mcp.json in TARGET_REPO
#   4. Prints next steps
# =============================================================================

set -euo pipefail

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
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
LOCAL_SKILL="${REPO_ROOT}/.claude/skills/codekg/SKILL.md"

# The target repo is where the user ran the script from (CWD), unless we're
# running from inside the code_kg repo itself (in which case we still use CWD).
TARGET_REPO="${PWD}"

echo "╔══════════════════════════════════════════════════╗"
echo "║       CodeKG Skill Installer                     ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Installing for: Claude Code (~/.claude/skills) + Kilo Code (~/.kilocode/skills) + other agents (~/.agents/skills)"
echo ""

# ── Install to each target directory ─────────────────────────────────────────
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

# ── Inject codekg into .mcp.json in the target repo ──────────────────────────
echo ""
echo "→ Configuring MCP server in: ${TARGET_REPO}/.mcp.json"

MCP_JSON="${TARGET_REPO}/.mcp.json"

# Detect the codekg-mcp binary: prefer venv inside target repo, fall back to
# poetry run (for repos that use poetry without in-project venv), then PATH.
CODEKG_BIN=""
if [ -x "${TARGET_REPO}/.venv/bin/codekg-mcp" ]; then
    CODEKG_BIN="${TARGET_REPO}/.venv/bin/codekg-mcp"
elif command -v codekg-mcp &>/dev/null; then
    CODEKG_BIN="$(command -v codekg-mcp)"
elif command -v poetry &>/dev/null && (cd "${TARGET_REPO}" && poetry run codekg-mcp --help &>/dev/null 2>&1); then
    # Resolve the actual path inside poetry's managed venv
    CODEKG_BIN="$(cd "${TARGET_REPO}" && poetry run which codekg-mcp 2>/dev/null || true)"
fi

if [ -z "$CODEKG_BIN" ]; then
    echo "  ⚠ codekg-mcp not found in .venv, PATH, or poetry venv."
    echo "    Install it first:"
    echo '      poetry add "code-kg[mcp] @ git+https://github.com/suchanek/code_kg.git"'
    echo "    Then re-run this script to inject the MCP config."
else
    # Determine DB paths (use existing files if present, else defaults)
    SQLITE_DB="${TARGET_REPO}/codekg.sqlite"
    LANCEDB_DIR="${TARGET_REPO}/lancedb"
    # Also check for codekg_lancedb (alternate naming convention)
    if [ -d "${TARGET_REPO}/codekg_lancedb" ] && [ ! -d "${LANCEDB_DIR}" ]; then
        LANCEDB_DIR="${TARGET_REPO}/codekg_lancedb"
    fi

    # Build the codekg server JSON block
    CODEKG_ENTRY=$(cat <<EOF
    "codekg": {
      "command": "${CODEKG_BIN}",
      "args": [
        "--repo",    "${TARGET_REPO}",
        "--db",      "${SQLITE_DB}",
        "--lancedb", "${LANCEDB_DIR}"
      ]
    }
EOF
)

    if [ ! -f "$MCP_JSON" ]; then
        # Create a fresh .mcp.json
        cat > "$MCP_JSON" <<EOF
{
  "mcpServers": {
${CODEKG_ENTRY}
  }
}
EOF
        echo "  ✓ Created ${MCP_JSON} with codekg entry"

    elif grep -q '"codekg"' "$MCP_JSON"; then
        echo "  ✓ codekg entry already present in ${MCP_JSON} — skipping"

    else
        # Append codekg to existing mcpServers using Python (available everywhere)
        python3 - "$MCP_JSON" "$CODEKG_BIN" "$TARGET_REPO" "$SQLITE_DB" "$LANCEDB_DIR" <<'PYEOF'
import json, sys

mcp_json_path = sys.argv[1]
codekg_bin    = sys.argv[2]
target_repo   = sys.argv[3]
sqlite_db     = sys.argv[4]
lancedb_dir   = sys.argv[5]

with open(mcp_json_path, "r") as f:
    data = json.load(f)

if "mcpServers" not in data:
    data["mcpServers"] = {}

data["mcpServers"]["codekg"] = {
    "command": codekg_bin,
    "args": [
        "--repo",    target_repo,
        "--db",      sqlite_db,
        "--lancedb", lancedb_dir,
    ]
}

with open(mcp_json_path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF
        echo "  ✓ Added codekg entry to ${MCP_JSON}"
    fi
fi

echo ""
echo "══════════════════════════════════════════════════"
echo "  CodeKG skill installed successfully!"
echo "  Works in: Claude Code and Kilo Code (VS Code)"
echo "══════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo ""
echo "  1. Install code-kg in your project (if not already done):"
echo '     poetry add "code-kg[mcp] @ git+https://github.com/suchanek/code_kg.git"'
echo ""
echo "  2. Build the knowledge graph (if not already done):"
echo "     poetry run codekg-build-sqlite  --repo . --db codekg.sqlite"
echo "     poetry run codekg-build-lancedb --sqlite codekg.sqlite --lancedb ./lancedb"
echo ""
echo "  3. Configure your AI agent:"
echo ""
echo "     GitHub Copilot (per-repo):"
echo "       Add codekg entry to .vscode/mcp.json (uses 'servers' key, not 'mcpServers')"
echo "       VS Code will prompt you to trust the server on first start"
echo ""
echo "     Kilo Code / Claude Code (per-repo, recommended):"
echo "       .mcp.json was updated above (or create it with the codekg entry)"
echo "       Run /setup-mcp inside Kilo Code for automated setup"
echo ""
echo "     Cline (global config only):"
echo "       Edit: ~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
echo "       Add a named entry: codekg-REPONAME (unique per repo)"
echo ""
echo "  4. Reload your AI agent / MCP servers to pick up the new config."
echo ""
echo "  Full docs: https://github.com/suchanek/code_kg/blob/main/docs/MCP.md"
