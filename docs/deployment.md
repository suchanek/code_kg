# CodeKG Deployment Guide

*Author: Eric G. Suchanek, PhD*

---

## Overview

CodeKG has two distinct deployment surfaces:

| Surface | What it is | Best options |
|---|---|---|
| **Python library + CLI** | `code_kg` package + 5 CLI entry points | PyPI, Conda, GitHub Releases |
| **Streamlit web app** | `app.py` interactive graph explorer | Docker, Streamlit Cloud, Fly.io |

These can be deployed independently or together. The sections below cover each option in detail.

---

## Option 1 — PyPI (Recommended for the library)

The project is already structured perfectly for PyPI: `pyproject.toml` with Poetry, proper `packages` declaration, classifiers, keywords, entry points, and a README.

### 1a. Prepare for release

```bash
# Bump version in pyproject.toml and src/code_kg/__init__.py
# e.g. 0.1.0 → 0.2.0

# Ensure the lock file is current
poetry lock

# Run tests
poetry run pytest

# Build sdist + wheel
poetry build
# → dist/code_kg-0.1.0.tar.gz
# → dist/code_kg-0.1.0-py3-none-any.whl
```

### 1b. Publish to TestPyPI first

```bash
poetry config repositories.testpypi https://test.pypi.org/legacy/
poetry publish --repository testpypi
```

Verify the install:

```bash
pip install --index-url https://test.pypi.org/simple/ code-kg
```

### 1c. Publish to PyPI

```bash
poetry publish
# prompts for PyPI credentials (or use POETRY_PYPI_TOKEN_PYPI env var)
```

After publishing, users install with:

```bash
pip install code-kg
```

All five CLI commands become available immediately:

```
codekg-build-sqlite
codekg-build-lancedb
codekg-query
codekg-pack
codekg-viz
```

### 1d. Automate with GitHub Actions

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - "v*"

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install poetry
      - run: poetry install --no-dev
      - run: poetry build
      - run: poetry publish
        env:
          POETRY_PYPI_TOKEN_PYPI: ${{ secrets.PYPI_TOKEN }}
```

Tag a release to trigger:

```bash
git tag v0.1.0
git push origin v0.1.0
```

---

## Option 2 — Docker (Recommended for the Streamlit app)

Docker packages the Streamlit app (`app.py`) with all heavy dependencies
(`sentence-transformers`, `lancedb`, `pyvis`) into a single portable image.

### 2a. Dockerfile

Create `Dockerfile` at the project root:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System deps for sentence-transformers / torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.8.3

# Copy dependency files first (layer cache)
COPY pyproject.toml poetry.lock ./

# Install runtime deps only (no dev tools)
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

# Copy source
COPY src/ ./src/
COPY app.py ./

# Expose Streamlit port
EXPOSE 8501

# Streamlit config: disable telemetry, set server options
ENV STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

ENTRYPOINT ["streamlit", "run", "app.py", "--server.headless=true"]
```

### 2b. docker-compose.yml (with persistent data volumes)

```yaml
version: "3.9"

services:
  codekg:
    build: .
    image: codekg:latest
    ports:
      - "8501:8501"
    volumes:
      # Mount your repo for analysis
      - ${REPO_ROOT:-./}:/workspace:ro
      # Persist the SQLite graph and LanceDB index
      - codekg-data:/data
    environment:
      - CODEKG_DB=/data/codekg.sqlite
      - CODEKG_LANCEDB=/data/lancedb

volumes:
  codekg-data:
```

### 2c. Build and run

```bash
# Build
docker build -t codekg:latest .

# Run (mount current repo for analysis)
docker run -p 8501:8501 \
  -v $(pwd):/workspace:ro \
  -v codekg-data:/data \
  codekg:latest

# Or with compose
REPO_ROOT=/path/to/your/repo docker compose up
```

Open `http://localhost:8501` in your browser.

### 2d. Publish to Docker Hub / GHCR

```bash
# Docker Hub
docker tag codekg:latest suchanek/codekg:0.1.0
docker push suchanek/codekg:0.1.0

# GitHub Container Registry (free for public repos)
docker tag codekg:latest ghcr.io/suchanek/codekg:0.1.0
docker push ghcr.io/suchanek/codekg:0.1.0
```

Automate via GitHub Actions (`.github/workflows/docker.yml`):

```yaml
name: Build & Push Docker image

on:
  push:
    tags: ["v*"]

jobs:
  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v5
        with:
          push: true
          tags: ghcr.io/suchanek/codekg:${{ github.ref_name }}
```

---

## Option 3 — Streamlit Community Cloud (Zero-infra for the app)

The fastest way to share the Streamlit app publicly — free tier available.

1. Push the repo to GitHub (already done: `github.com/suchanek/code_kg`)
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Select repo `suchanek/code_kg`, branch `main`, main file `app.py`
4. Add a `requirements.txt` (Streamlit Cloud doesn't use Poetry directly):

```bash
# Generate from poetry
poetry export -f requirements.txt --without-hashes -o requirements.txt
```

**Limitation:** Streamlit Cloud has no persistent filesystem — the SQLite/LanceDB
artifacts won't survive restarts. Best suited for demos with a pre-built DB
committed to the repo or stored in cloud storage (S3, GCS).

---

## Option 4 — Fly.io (Lightweight cloud VM for the app)

Fly.io runs Docker containers globally with persistent volumes — a good middle
ground between Streamlit Cloud and a full Kubernetes cluster.

```bash
# Install flyctl
brew install flyctl
fly auth login

# From the repo root (uses the Dockerfile above)
fly launch --name codekg --region iad --dockerfile Dockerfile

# Add a persistent volume for SQLite + LanceDB
fly volumes create codekg_data --size 10 --region iad

# Deploy
fly deploy
```

Add to `fly.toml`:

```toml
[mounts]
  source = "codekg_data"
  destination = "/data"

[[services]]
  internal_port = 8501
  protocol = "tcp"

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]
  [[services.ports]]
    port = 80
    handlers = ["http"]
```

---

## Option 5 — GitHub Releases (Binary artifacts)

For users who want pre-built wheels without PyPI:

```bash
# Build
poetry build

# Create a GitHub release and attach artifacts
gh release create v0.1.0 dist/* \
  --title "CodeKG v0.1.0" \
  --notes "Initial release"
```

Users install directly from the release:

```bash
pip install https://github.com/suchanek/code_kg/releases/download/v0.1.0/code_kg-0.1.0-py3-none-any.whl
```

---

## Option 6 — MCP Server (Emerging AI tooling integration)

CodeKG's hybrid query + snippet pack API maps naturally onto the
[Model Context Protocol](https://modelcontextprotocol.io/) — exposing
`codekg-query` and `codekg-pack` as MCP tools lets any MCP-compatible
agent (Claude, Cursor, etc.) query your codebase knowledge graph directly.

A minimal `mcp_server.py` sketch:

```python
from mcp.server.fastmcp import FastMCP
from code_kg import CodeKG

mcp = FastMCP("codekg")
kg = CodeKG(repo_root=".", db_path="codekg.sqlite", lancedb_dir="./lancedb")

@mcp.tool()
def query_codebase(q: str, k: int = 8, hop: int = 1) -> str:
    """Hybrid semantic + structural query over the codebase knowledge graph."""
    result = kg.query(q, k=k, hop=hop)
    return result.to_json()

@mcp.tool()
def pack_snippets(q: str, k: int = 8, hop: int = 1) -> str:
    """Return source-grounded code snippets relevant to a query."""
    pack = kg.pack(q, k=k, hop=hop)
    return pack.to_markdown()

if __name__ == "__main__":
    mcp.run()
```

Register in `pyproject.toml`:

```toml
[tool.poetry.scripts]
codekg-mcp = "code_kg.mcp_server:main"
```

---

## Recommended Deployment Strategy

| Goal | Recommended path |
|---|---|
| Share the library with the Python community | **PyPI** (Option 1) |
| Run the Streamlit app locally / on a server | **Docker + docker-compose** (Option 2) |
| Quick public demo, no infra | **Streamlit Community Cloud** (Option 3) |
| Persistent cloud deployment | **Fly.io** (Option 4) |
| Distribute pre-built wheels without PyPI | **GitHub Releases** (Option 5) |
| Integrate with AI agents / IDEs | **MCP Server** (Option 6) |

### Suggested release order

1. **PyPI first** — the `pyproject.toml` is already complete; `poetry build && poetry publish` is all it takes.
2. **Docker image** — build from the Dockerfile above and push to GHCR alongside the PyPI release.
3. **MCP server** — add as a CLI entry point so agent users get it automatically with `pip install code-kg`.

---

## Pre-release Checklist

- [ ] Bump `version` in `pyproject.toml` and `src/code_kg/__init__.py`
- [ ] Update `CHANGELOG.md`
- [ ] Run `poetry run pytest` — all tests green
- [ ] Run `poetry run ruff check src/` — no lint errors
- [ ] Run `poetry build` — wheel and sdist build cleanly
- [ ] Test install in a fresh venv: `pip install dist/code_kg-*.whl`
- [ ] Smoke-test all 5 CLI entry points
- [ ] `git tag v0.1.0 && git push origin v0.1.0`
- [ ] `poetry publish` (or let GitHub Actions do it)
- [ ] `docker build -t codekg:latest . && docker push ghcr.io/suchanek/codekg:latest`
