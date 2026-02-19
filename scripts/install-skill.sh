#!/usr/bin/env bash
# =============================================================================
# install-skill.sh — Bootstrap the CodeKG skill on a new machine
#
# Installs to:
#   ~/.claude/skills/codekg/    (Claude Code — ~/.claude/commands/ for slash cmds)
#   ~/.kilocode/skills/codekg/  (Kilo Code — ~/.kilocode/skills/ for agent skills)
#   ~/.agents/skills/codekg/    (other agents)
#
# Usage (from the code_kg repo root):
#   bash scripts/install-skill.sh
#
# Usage (one-liner, no clone needed):
#   curl -fsSL https://raw.githubusercontent.com/suchanek/code_kg/main/scripts/install-skill.sh | bash
#
# What it does:
#   1. Creates skill directories for Claude Code, Kilo Code, and other agents
#   2. Downloads SKILL.md and references/installation.md from GitHub
#      (or copies from local repo if running from within the clone)
#   3. Prints next steps
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

echo ""
echo "══════════════════════════════════════════════════"
echo "  CodeKG skill installed successfully!"
echo "  Works in: Claude Code and Kilo Code (VS Code)"
echo "══════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo ""
echo "  1. Install code-kg in your project:"
echo '     poetry add "code-kg[mcp] @ git+https://github.com/suchanek/code_kg.git"'
echo ""
echo "  2. Build the knowledge graph:"
echo "     poetry run codekg-build-sqlite  --repo . --db codekg.sqlite"
echo "     poetry run codekg-build-lancedb --sqlite codekg.sqlite --lancedb ./lancedb"
echo ""
echo "  3. Configure your AI agent:"
echo ""
echo "     Kilo Code / Claude Code (per-repo, recommended):"
echo "       Add codekg entry to .mcp.json in your project root"
echo "       Run /setup-mcp inside Kilo Code for automated setup"
echo ""
echo "     Cline (global config only):"
echo "       Edit: ~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
echo "       Add a named entry: codekg-REPONAME (unique per repo)"
echo "       Copy .clinerules template to your repo root:"
echo "         cp ${REPO_ROOT}/.claude/skills/codekg/clinerules.md /path/to/myrepo/.clinerules"
echo ""
echo "  Full docs: https://github.com/suchanek/code_kg/blob/main/docs/MCP.md"
