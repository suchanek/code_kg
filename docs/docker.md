# CodeKG Docker Setup

*Author: Eric G. Suchanek, PhD*

---

## Overview

CodeKG ships a **Streamlit web application** (`app.py`) that provides an interactive knowledge-graph explorer for Python codebases. The Docker setup packages this app — together with all heavy dependencies (`sentence-transformers`, `lancedb`, `pyvis`, `torch`) — into a single portable image that can be run anywhere Docker is available.

The image is built on `python:3.11-slim`, installs dependencies via **Poetry 2.x**, and stores all generated artefacts (SQLite graph, LanceDB vector index) in a named Docker volume so data persists across container restarts.

```
┌─────────────────────────────────────────────────────────┐
│  Host machine                                           │
│                                                         │
│  /path/to/repo  ──(read-only)──▶  /workspace  ┐        │
│                                                │        │
│  Docker volume codekg-data ◀──────────────────┤        │
│    /data/codekg.sqlite                         │        │
│    /data/lancedb/                              │        │
│                                                │        │
│  localhost:8501 ◀──────────────────────────────┘        │
└─────────────────────────────────────────────────────────┘
```

## Files Created

| File | Purpose |
|---|---|
| `Dockerfile` | Multi-stage-friendly single-stage image definition |
| `docker-compose.yml` | Orchestrates the service with volumes, env vars, and healthcheck |
| `.dockerignore` | Keeps the build context lean (excludes caches, venvs, generated artefacts) |
| `.streamlit/config.toml` | Baked-in Streamlit server config (headless, dark theme, telemetry off) |

### `Dockerfile` — annotated

```dockerfile
FROM python:3.11-slim          # slim base keeps the image small

WORKDIR /app

# System deps: compiler for C extensions, curl for healthcheck, git for HF model downloads
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git && rm -rf /var/lib/apt/lists/*

# Pin Poetry to the same major version used locally (2.x lock-file format)
RUN pip install --no-cache-dir "poetry==2.0.1"

# Copy manifests + README first → Docker caches this layer until deps change
COPY pyproject.toml poetry.lock README.md ./

# Install runtime deps only; --no-root skips installing the code_kg package
# itself (src/ is COPY-ed in the next step and lands on sys.path directly)
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-root --no-interaction --no-ansi

# Source code (invalidates only when code changes, not when deps change)
COPY src/ ./src/
COPY app.py ./
COPY .streamlit/ ./.streamlit/

# Env vars — picked up by app.py defaults and Streamlit server
ENV STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    CODEKG_DB=/data/codekg.sqlite \
    CODEKG_LANCEDB=/data/lancedb \
    PYTHONUNBUFFERED=1 \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", "--server.headless=true"]
```

**Key design decisions:**

- **`--no-root`** — Poetry 2.x tries to install the project package itself during `poetry install`. Since we `COPY src/` separately (and it lands on `sys.path` via the working directory), we skip this step to avoid needing the full package metadata at install time.
- **`README.md` in the dep layer** — `pyproject.toml` declares `readme = "README.md"`, so Poetry validates its presence even with `--no-root`. It is copied alongside the manifests so the dep-cache layer remains valid.
- **Layer ordering** — `pyproject.toml` / `poetry.lock` are copied before source files. A source-only change rebuilds only the last two `COPY` layers (~seconds), not the full dep install (~minutes).
- **Poetry version pinned** — The lock-file format changed between Poetry 1.x and 2.x. The Dockerfile pins `poetry==2.0.1` to match the version used locally; regenerate `poetry.lock` with the same version if you upgrade.

---

## Quick Start

### Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin) installed and running
- The `poetry.lock` file committed and up-to-date (`poetry lock` if in doubt)

### Build the image

```bash
docker build -t codekg:latest .
```

The first build takes several minutes (downloading the base image and installing `sentence-transformers` / `torch`). Subsequent builds with only source-code changes complete in seconds thanks to layer caching.

### Run with `docker run`

```bash
# Analyse the current directory, persist data in a named volume
docker run -p 8501:8501 \
  -v $(pwd):/workspace:ro \
  -v codekg-data:/data \
  codekg:latest
```

Open **http://localhost:8501** in your browser.

If port 8501 is already in use, map to a different host port:

```bash
docker run -p 8510:8501 \
  -v $(pwd):/workspace:ro \
  -v codekg-data:/data \
  codekg:latest
```

---

## Docker Compose

`docker-compose.yml` is the recommended way to run CodeKG because it handles volume creation, environment variables, and restart policy automatically.

```yaml
services:
  codekg:
    build: .
    image: codekg:latest
    container_name: codekg
    restart: unless-stopped
    ports:
      - "${CODEKG_PORT:-8501}:8501"   # override with CODEKG_PORT=8510
    volumes:
      - ${REPO_ROOT:-./}:/workspace:ro  # repo to analyse (read-only)
      - codekg-data:/data               # persistent graph + index
    environment:
      - CODEKG_DB=/data/codekg.sqlite
      - CODEKG_LANCEDB=/data/lancedb
      - STREAMLIT_SERVER_PORT=8501
      - STREAMLIT_SERVER_ADDRESS=0.0.0.0
      - STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

volumes:
  codekg-data:
    driver: local
```

### Common compose commands

```bash
# Start (build if needed, detached)
docker compose up -d

# Start against a specific repo
REPO_ROOT=/path/to/your/repo docker compose up -d

# Use a different host port (e.g. if 8501 is taken)
CODEKG_PORT=8510 docker compose up -d

# View logs
docker compose logs -f

# Stop and remove the container (volume is preserved)
docker compose down

# Stop and remove the container AND the data volume (full reset)
docker compose down -v
```

---

## Persistent Data Volumes

All generated artefacts are stored in the named Docker volume **`codekg-data`**, mounted at `/data` inside the container:

| Path inside container | Contents |
|---|---|
| `/data/codekg.sqlite` | SQLite knowledge graph (nodes + edges) |
| `/data/lancedb/` | LanceDB vector index |

The volume survives `docker compose down` and `docker restart`. To inspect or back up the data:

```bash
# List volume details
docker volume inspect code_kg_codekg-data

# Copy the SQLite file to the host
docker run --rm \
  -v code_kg_codekg-data:/data \
  -v $(pwd):/out \
  python:3.11-slim \
  cp /data/codekg.sqlite /out/codekg.sqlite
```

To start fresh (wipe all graph data):

```bash
docker compose down -v   # removes the codekg-data volume
docker compose up -d     # recreates it empty
```

---

## Environment Variables

All variables can be set in the shell, in a `.env` file alongside `docker-compose.yml`, or passed with `-e` to `docker run`.

| Variable | Default (in container) | Description |
|---|---|---|
| `CODEKG_DB` | `/data/codekg.sqlite` | Path to the SQLite knowledge graph |
| `CODEKG_LANCEDB` | `/data/lancedb` | Directory for the LanceDB vector index |
| `CODEKG_PORT` | `8501` | Host port mapped to the container's 8501 (compose only) |
| `REPO_ROOT` | `./` (project root) | Host path mounted read-only at `/workspace` (compose only) |
| `STREAMLIT_SERVER_PORT` | `8501` | Streamlit internal port (do not change) |
| `STREAMLIT_SERVER_ADDRESS` | `0.0.0.0` | Bind address (do not change) |
| `STREAMLIT_BROWSER_GATHER_USAGE_STATS` | `false` | Disable Streamlit telemetry |
| `PYTHONUNBUFFERED` | `1` | Unbuffered stdout/stderr for clean Docker logs |
| `HF_HUB_DISABLE_SYMLINKS_WARNING` | `1` | Suppress HuggingFace symlink warning in containers |

### `.env` file example

```dotenv
REPO_ROOT=/Users/me/projects/myapp
CODEKG_PORT=8501
```

Place this file in the project root and `docker compose up` will pick it up automatically.

---

## In-App Workflow

Once the container is running, open **http://localhost:8501** (or your chosen port).

### 1. Set paths in the sidebar

The sidebar pre-populates from environment variables:

| Sidebar field | Default value (Docker) | Notes |
|---|---|---|
| **SQLite path** | `/data/codekg.sqlite` | From `CODEKG_DB` env var |
| **Repo root** | `/workspace` | Set this to `/workspace` to analyse the mounted repo |
| **LanceDB dir** | `/data/lancedb` | From `CODEKG_LANCEDB` env var |

> **Important:** Set **Repo root** to `/workspace` (the read-only mount) before building the graph.

### 2. Build the knowledge graph

Click **⚡ Build All (graph + index)** in the sidebar to run the full pipeline:

```
/workspace  →  AST extraction  →  /data/codekg.sqlite  →  /data/lancedb/
```

This may take 1–5 minutes depending on repo size. The embedding step (LanceDB) is the slowest part; `sentence-transformers` downloads the model on first run and caches it inside the container.

### 3. Explore

| Tab | What it does |
|---|---|
| **🗺️ Graph Browser** | Interactive pyvis graph of the full knowledge graph; filter by node kind or module path |
| **🔍 Hybrid Query** | Natural-language query → semantic seeds → graph expansion → ranked node results |
| **📦 Snippet Pack** | Query → source-grounded code snippets suitable for LLM ingestion or human review |

### 4. Download results

Both the **Query** and **Snippet Pack** tabs offer download buttons for JSON and Markdown exports.

---

## Publishing the Image

### Docker Hub

```bash
docker tag codekg:latest suchanek/codekg:0.1.0
docker push suchanek/codekg:0.1.0
docker tag codekg:latest suchanek/codekg:latest
docker push suchanek/codekg:latest
```

### GitHub Container Registry (GHCR)

```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u suchanek --password-stdin
docker tag codekg:latest ghcr.io/suchanek/codekg:0.1.0
docker push ghcr.io/suchanek/codekg:0.1.0
```

### GitHub Actions (automated on tag push)

`.github/workflows/docker.yml`:

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

Trigger with:

```bash
git tag v0.1.0
git push origin v0.1.0
```

---

## Troubleshooting

### Port already in use

```
bind: address already in use
```

Use `CODEKG_PORT` to pick a free port:

```bash
CODEKG_PORT=8510 docker compose up -d
```

Or find and stop the conflicting process:

```bash
lsof -i :8501          # macOS / Linux
```

### `poetry.lock` incompatible with Poetry version

```
pyproject.toml changed significantly since poetry.lock was last generated.
```

Regenerate the lock file locally with the same Poetry version pinned in the Dockerfile:

```bash
pip install "poetry==2.0.1"
poetry lock
docker build -t codekg:latest .
```

### `README.md` not found during build

```
Readme path `/app/README.md` does not exist.
```

This means `.dockerignore` is excluding `README.md`. Ensure the file is **not** listed in `.dockerignore` (the current `.dockerignore` only excludes `CHANGELOG.md` and `docs/`, not `README.md`).

### Sentence-transformers model download fails

The first `Build Index` run downloads the embedding model from HuggingFace. If the container has no internet access, pre-download the model and bind-mount it:

```bash
# On the host
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
# Model is cached in ~/.cache/huggingface/

# Mount the cache into the container
docker run -p 8501:8501 \
  -v $(pwd):/workspace:ro \
  -v codekg-data:/data \
  -v ~/.cache/huggingface:/root/.cache/huggingface:ro \
  codekg:latest
```

### Container exits immediately

Check logs:

```bash
docker compose logs codekg
# or
docker logs codekg
```

Common causes: missing `poetry.lock`, Python import error in `app.py`, or a Streamlit version incompatibility.

### Graph not persisting between restarts

Verify the named volume exists and is mounted correctly:

```bash
docker volume ls | grep codekg
docker inspect codekg | grep -A5 Mounts
```

If the volume was accidentally deleted (`docker compose down -v`), rebuild the graph from the sidebar.

---

## Summary of All Docker-Related Files

```
code_kg/
├── Dockerfile                  ← image definition
├── docker-compose.yml          ← service orchestration
├── .dockerignore               ← build-context filter
├── .streamlit/
│   └── config.toml             ← baked-in Streamlit config
├── poetry.lock                 ← pinned dep versions (must be committed)
└── app.py                      ← reads CODEKG_DB / CODEKG_LANCEDB env vars
```
