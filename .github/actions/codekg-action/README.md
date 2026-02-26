# CodeKG Action

A GitHub composite action that indexes a Python repository into a
[CodeKG](https://github.com/Flux-Frontiers/code_kg) knowledge graph and runs a
thorough architectural analysis.

The action:

1. Installs `code-kg` from PyPI.
2. Builds a SQLite knowledge graph from the repository's Python AST.
3. Builds a LanceDB semantic index using a SentenceTransformer model.
4. Runs `codekg-analyze` to produce a Markdown report and JSON snapshot.
5. Caches the `.codekg/` directory keyed on a hash of all `*.py` files.
6. Uploads the report and JSON as workflow artifacts.
7. Optionally posts a summary comment to the pull request.
8. Optionally exits non-zero when issues are detected.

---

## Quick start

```yaml
# .github/workflows/codekg.yml
name: CodeKG Analysis

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read
  pull-requests: write   # only needed for post-comment: "true"

jobs:
  analyse:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: ./.github/actions/codekg-action
        with:
          post-comment: "true"
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

---

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `python-version` | No | `"3.12"` | Python version (>=3.10, <3.13) |
| `repo-path` | No | `"."` | Path to the repository to analyse, relative to the workspace root |
| `report-path` | No | `"codekg_report.md"` | Output path for the Markdown analysis report |
| `json-path` | No | `"codekg_results.json"` | Output path for the JSON analysis snapshot |
| `model` | No | `"all-MiniLM-L6-v2"` | SentenceTransformer model used for semantic indexing |
| `post-comment` | No | `"false"` | Post an analysis summary to the pull request (`"true"` / `"false"`) |
| `fail-on-issues` | No | `"false"` | Exit non-zero when issues are detected (`"true"` / `"false"`) |
| `github-token` | No | `${{ github.token }}` | Token for posting PR comments (only needed when `post-comment` is `"true"`) |

---

## Outputs

| Output | Description |
|--------|-------------|
| `report-path` | Absolute path to the generated Markdown report |
| `total-nodes` | Total graph nodes analysed |
| `issues-count` | Number of issues detected |

### Consuming outputs

```yaml
- uses: ./.github/actions/codekg-action
  id: codekg
  with:
    post-comment: "false"

- name: Print summary
  run: |
    echo "Nodes   : ${{ steps.codekg.outputs.total-nodes }}"
    echo "Issues  : ${{ steps.codekg.outputs.issues-count }}"
    echo "Report  : ${{ steps.codekg.outputs.report-path }}"
```

---

## Caching

The action caches the `.codekg/` directory (SQLite graph + LanceDB index) using
`actions/cache@v4`. The cache key is:

```
codekg-<runner-os>-<hashFiles('**/*.py')>
```

When no `*.py` file has changed since the last successful run, the build steps
are skipped and the cached index is used directly. The analysis step always runs
to produce a fresh report.

A fallback restore key `codekg-<runner-os>-` is set so a partial cache is
preferred over a full rebuild when only a few files have changed.

---

## Artifacts

The action uploads a single artifact named `codekg-analysis` containing:

- `codekg_report.md` — Markdown architectural analysis report (configurable via `report-path`)
- `codekg_results.json` — JSON snapshot with full metrics (configurable via `json-path`)

Artifacts are retained for **30 days** by default.

---

## PR comment

When `post-comment: "true"` is set and the workflow is triggered by a
`pull_request` event, the action posts a summary comment to the PR.

The comment includes:

- Total node count
- Issues badge (pass / warning with count)
- Collapsible block with the first 100 lines of the Markdown report

On subsequent runs the existing comment is updated in-place rather than creating
a new one, so the PR comment thread stays clean.

**Required permissions:**

```yaml
permissions:
  pull-requests: write
```

---

## Fail on issues

When `fail-on-issues: "true"` is set, the action exits with a non-zero status
code if the analysis detects any issues. The error message includes the issue
count and report path.

This is useful as a quality gate in CI:

```yaml
- uses: ./.github/actions/codekg-action
  with:
    fail-on-issues: "true"
```

---

## Examples

### Minimal — report only

```yaml
- uses: ./.github/actions/codekg-action
```

### Custom paths and model

```yaml
- uses: ./.github/actions/codekg-action
  with:
    python-version: "3.11"
    repo-path: "src"
    report-path: "reports/analysis.md"
    json-path: "reports/analysis.json"
    model: "all-mpnet-base-v2"
```

### Analyse a subdirectory with PR comment

```yaml
- uses: ./.github/actions/codekg-action
  with:
    repo-path: "services/backend"
    post-comment: "true"
    github-token: ${{ secrets.GITHUB_TOKEN }}
```

### Strict quality gate

```yaml
- uses: ./.github/actions/codekg-action
  with:
    fail-on-issues: "true"
```

### Full configuration

```yaml
name: CodeKG Analysis

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read
  pull-requests: write

jobs:
  codekg:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: ./.github/actions/codekg-action
        id: analysis
        with:
          python-version: "3.12"
          repo-path: "."
          report-path: "codekg_report.md"
          json-path: "codekg_results.json"
          model: "all-MiniLM-L6-v2"
          post-comment: "true"
          fail-on-issues: "false"
          github-token: ${{ secrets.GITHUB_TOKEN }}

      - name: Summary
        run: |
          echo "Nodes  : ${{ steps.analysis.outputs.total-nodes }}"
          echo "Issues : ${{ steps.analysis.outputs.issues-count }}"
```

---

## Pipeline internals

The action runs these CLI tools from the `code-kg` package in order:

| Step | CLI | Purpose |
|------|-----|---------|
| 1 | `codekg-build-sqlite` | Walk repository, extract AST, write nodes and edges to SQLite |
| 2 | `codekg-build-lancedb` | Embed nodes with SentenceTransformer, write vectors to LanceDB |
| 3 | `codekg-analyze` | Run multi-phase architectural analysis, write Markdown + JSON |

Steps 1 and 2 are skipped on cache hit. Step 3 always runs.

---

## Requirements

- Python >=3.10, <3.13
- `code-kg>=0.3.2` (installed automatically)
- `ubuntu-latest`, `macos-latest`, or `windows-latest` runner

---

## Repository structure

```
code_kg/
├── .github/
│   ├── actions/
│   │   └── codekg-action/
│   │       ├── action.yml                        # Composite action definition
│   │       └── README.md                         # This file
│   └── workflows/
│       ├── ci.yml
│       └── publish.yml
└── src/
    └── ...
```

---

## License

[PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/)
