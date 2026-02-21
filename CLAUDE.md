# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Agent Identity

This Claude instance holds a unique distinction: it is the **first CodeKG-equipped AI agent** — the original agent that built, tested, and runs on the very knowledge graph infrastructure described in this repository. The MCP tools (`graph_stats`, `query_codebase`, `pack_snippets`, `get_node`) are not external utilities here; they are a live index of this codebase, and this agent is their first real user.

Always use the CodeKG MCP tools before reading files. You have direct, source-grounded access to this codebase — use it.

---

## Project Overview

**Name:** code_kg
**Description:** A tool that indexes Python codebases into a knowledge graph and exposes it via MCP for AI agents
**Stack:** Python/Poetry

---

## Claude Copilot

This project uses [Claude Copilot](https://github.com/Everyone-Needs-A-Copilot/claude-copilot).

**Full documentation:** `~/.claude/copilot/README.md`

### Commands

| Command | Purpose |
|---------|---------|
| `/protocol` | Start fresh work with Agent-First Protocol |
| `/continue` | Resume previous work via Memory Copilot |
| `/setup-project` | Initialize Claude Copilot in a new project |
| `/knowledge-copilot` | Build or link shared knowledge repository |

### Capabilities

| Capability | Tools | Purpose |
|------------|-------|---------|
| **Memory** | `initiative_*`, `memory_*` | Persist decisions, lessons, progress across sessions |
| **Agents** | 11 specialists via `/protocol` | Expert guidance routed by task type |
| **Knowledge** | `knowledge_search`, `knowledge_get` | Search company/product documentation |
| **Skills** | `skill_search`, `skill_get` | Load expertise on demand |
| **CodeKG** | `graph_stats`, `query_codebase`, `pack_snippets`, `get_node` | Source-grounded codebase exploration via MCP |

### Agents

| Agent | Domain |
|-------|--------|
| `ta` | Tech Architect - system design, task breakdown |
| `me` | Engineer - code implementation |
| `qa` | QA - testing, edge cases |
| `sec` | Security - vulnerabilities, OWASP |
| `doc` | Documentation - technical writing |
| `do` | DevOps - CI/CD, infrastructure |
| `sd` | Service Designer - customer journeys |
| `uxd` | UX Designer - interaction design |
| `uids` | UI Designer - visual design |
| `uid` | UI Developer - component implementation |
| `cw` | Copywriter - microcopy, voice |
| `kc` | Knowledge Copilot - shared knowledge setup |

### Configuration

| Component | Status |
|-----------|--------|
| Memory | Workspace: `code_kg` |
| Knowledge | Not configured |
| Skills | Local: `.claude/skills/` |

---

## Session Management

**Start:** `/protocol` - Activates Agent-First Protocol

**Resume:** `/continue` - Loads from Memory Copilot

**End:** Call `initiative_update` with completed tasks, decisions, lessons, and resume instructions

---

## Project-Specific Rules

### No Time Estimates
All plans, roadmaps, and task breakdowns MUST omit time estimates. Use phases, priorities, complexity ratings, and dependencies instead of dates or durations. See `~/.claude/copilot/CLAUDE.md` for full policy.

- Prefer `:param:` style docstrings
