#!/usr/bin/env bash
# =============================================================================
# install-skill.sh — Bootstrap the CodeKG Claude skill on a new machine
#
# Usage (from the code_kg repo root):
#   bash scripts/install-skill.sh
#
# Usage (one-liner, no clone needed):
#   curl -fsSL https://raw.githubusercontent.com/suchanek/code_kg/main/scripts/install-skill.sh | bash
#
# What it does:
#   1. Creates ~/.claude/skills/codekg/
#   2. Downloads SKILL.md and references/installation.md from GitHub
#      (or copies from local repo if running from within the clone)
#   3. Prints next steps
# =============================================================================

set -euo pipefail

REPO="suchanek/code_kg"
BRANCH="main"
RAW_BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
SKILL_DIR="${HOME}/.claude/skills/codekg"
REFS_DIR="${SKILL_DIR}/references"

# ── Detect if we're running from inside the repo ─────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
LOCAL_SKILL="${REPO_ROOT}/.claude/skills/codekg/SKILL.md"

echo "╔══════════════════════════════════════════════════╗"
echo "║       CodeKG Skill Installer                     ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Create target directories ─────────────────────────────────────────────────
mkdir -p "$SKILL_DIR"
mkdir -p "$REFS_DIR"

# ── Copy or download ──────────────────────────────────────────────────────────
if [ -f "$LOCAL_SKILL" ]; then
    echo "→ Local repo detected at: $REPO_ROOT"
    echo "  Copying skill files from local clone..."
    cp "${REPO_ROOT}/.claude/skills/codekg/SKILL.md" "${SKILL_DIR}/SKILL.md"
    cp "${REPO_ROOT}/.claude/skills/codekg/references/installation.md" "${REFS_DIR}/installation.md"
else
    echo "→ No local clone detected. Downloading from GitHub..."
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

# ── Verify ────────────────────────────────────────────────────────────────────
if [ ! -f "${SKILL_DIR}/SKILL.md" ] || [ ! -f "${REFS_DIR}/installation.md" ]; then
    echo "ERROR: Installation failed — files not found after copy/download."
    exit 1
fi

echo ""
echo "✓ Installed: ${SKILL_DIR}/SKILL.md"
echo "✓ Installed: ${REFS_DIR}/installation.md"
echo ""
echo "══════════════════════════════════════════════════"
echo "  CodeKG skill installed successfully!"
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
echo "  3. Configure Claude Code (.mcp.json) — see docs/MCP.md for the snippet"
echo "     Or run /setup-mcp inside Claude Code for automated setup"
echo ""
echo "  Full docs: https://github.com/suchanek/code_kg/blob/main/docs/MCP.md"
