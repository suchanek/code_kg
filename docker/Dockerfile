# ============================================================
# CodeKG — Streamlit app image
# ============================================================
# Build:  docker build -t codekg:latest .
# Run:    docker run -p 8501:8501 -v $(pwd):/workspace:ro -v codekg-data:/data codekg:latest
# ============================================================

FROM python:3.11-slim

LABEL org.opencontainers.image.title="CodeKG" \
      org.opencontainers.image.description="Interactive knowledge-graph explorer for Python codebases" \
      org.opencontainers.image.authors="Eric G. Suchanek, PhD <suchanek@mac.com>" \
      org.opencontainers.image.source="https://github.com/suchanek/code_kg" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

# ── System deps ──────────────────────────────────────────────
# build-essential  → compiles C extensions (numpy, tokenizers, etc.)
# curl             → healthcheck probe
# git              → sentence-transformers may clone model repos
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

# ── Poetry ───────────────────────────────────────────────────
# Pin the version so the image is reproducible.
# Must match the major version used to generate poetry.lock locally.
RUN pip install --no-cache-dir "poetry==2.0.1"

# ── Python dependencies (cached layer) ───────────────────────
# Copy only the dependency manifests first so Docker can cache
# this layer independently of source-code changes.
# README.md is referenced by pyproject.toml so Poetry needs it present.
COPY pyproject.toml poetry.lock README.md ./

# Install runtime deps into the system Python (no virtualenv needed
# inside a container).  Skip dev extras (pytest, ruff, mypy).
# --no-root: don't install the code_kg package itself here; we COPY
#            src/ in the next step and it lands on sys.path via PYTHONPATH.
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-root --no-interaction --no-ansi

# ── Application source ────────────────────────────────────────
COPY src/ ./src/
COPY app.py ./

# ── Streamlit configuration ───────────────────────────────────
# Bake in a sensible server config; individual settings can still
# be overridden at runtime via environment variables.
COPY .streamlit/ ./.streamlit/

# ── Runtime environment ───────────────────────────────────────
# CODEKG_DB / CODEKG_LANCEDB are read by app.py defaults when
# the user hasn't set a custom path in the sidebar.
ENV STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    CODEKG_DB=/data/codekg.sqlite \
    CODEKG_LANCEDB=/data/lancedb \
    # Keep Python output unbuffered so logs appear immediately.
    PYTHONUNBUFFERED=1 \
    # Silence the HuggingFace symlink warning inside containers.
    HF_HUB_DISABLE_SYMLINKS_WARNING=1

EXPOSE 8501

# ── Healthcheck ───────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# ── Entrypoint ────────────────────────────────────────────────
ENTRYPOINT ["streamlit", "run", "app.py", "--server.headless=true"]
