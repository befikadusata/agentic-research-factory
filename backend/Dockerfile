FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# WeasyPrint system deps + curl for healthcheck, plus OpenCV's runtime libs
# (libgl1, libglib2.0-0). docling-ibm-models imports cv2 during layout
# prediction, so without them every PDF parse dies on
# "ImportError: libGL.so.1: cannot open shared object file" — which parse_pdf
# swallows into an empty chunk list, i.e. a silent no-op ingest.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi-dev libcairo2 libpangocairo-1.0-0 \
    libgl1 libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the EXACT locked versions (from uv.lock), not a fresh pyproject
# resolve. A fresh resolve picks an older crewai (dragged down by
# crewai-tools==0.14.0) that breaks Pydantic tool-schema generation at runtime;
# installing --frozen keeps the image identical to the tested dev environment.
#
# `uv sync` rather than `uv export | uv pip install`: the lock pins torch to the
# CPU-only build, which lives on PyTorch's own index. Flattening to a
# requirements.txt loses the per-package index routing that
# [tool.uv.sources] encodes — and re-adding it as a blanket --extra-index-url
# does not work, because that index also mirrors common packages (certifi et al)
# at versions the lock does not contain. `uv sync` reads the routing directly,
# so torch comes from the CPU index and everything else from PyPI.
#
# The venv lives at /opt/venv, NOT the default /app/.venv: Compose bind-mounts
# ./backend over /app for hot reload, which would shadow an in-project venv and
# leave the image's interpreter unreachable ("exec /app/.venv/bin/uvicorn: no
# such file or directory"). PATH covers every entrypoint — uvicorn here, alembic
# and celery via Compose commands.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Where the prefetched docling models live. Without this, the models baked in
# below are simply ignored: `docling-tools models download` writes a plain
# local_dir tree, but a DocumentConverter with artifacts_path unset resolves
# models through the HuggingFace *cache snapshot* API instead and fails with
# "cannot find the appropriate snapshot folder ... check your internet
# connection" — i.e. it downloads them all over again at parse time.
# DOCLING_ prefix is docling's own AppSettings env prefix.
ENV DOCLING_ARTIFACTS_PATH=/root/.cache/docling/models

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache

# Bake docling's models into the image. Left out, the FIRST PDF upload of every
# deployment downloads them (hundreds of MB) inside the parse — far longer than
# pdf_service's timeout, so the very first upload always ingests zero chunks.
#
# Two models, matching what pdf_service actually configures: tableformer for
# table structure, and the V2/"old" layout model. NOT the default layout model
# (docling-layout-heron): that is an RT-DETRv2 checkpoint, and the locked
# transformers 4.46.3 does not know that architecture — loading it dies with
# "does not recognize this architecture", which parse_pdf swallows into an empty
# ingest. See services/pdf_service.py for why the spec is pinned rather than the
# dependency bumped. No OCR model is fetched because pdf_service sets
# do_ocr=False; enrichment models (code_formula, picture_classifier) are in
# docling's predefined set but stay out — they sit behind options this app never
# enables and would add gigabytes to an image already watched for size.
#
# HF_HUB_DISABLE_XET is load-bearing. huggingface_hub prefers the xet transfer
# backend (hf_xet is installed transitively), which fans out over its own CAS
# endpoints — and that pattern does not survive BuildKit's network namespace.
# Measured here: the layout model pulls in 20s via the classic CDN and in a
# plain container over xet, but took 14-23 min inside a build layer, and
# tableformer wedged for 9h39m with no output. Same link, same image: it is the
# xet-in-BuildKit combination, not the network. The classic CDN path sustains
# 2.2 MB/s inside BuildKit.
#
# The timeouts remain as a backstop so a stalled fetch fails loudly instead of
# hanging a build forever. A failure here MUST fail the build — an image that
# silently shipped without these models would put the download back in the first
# upload's path, which is the whole bug this layer exists to prevent.
RUN HF_HUB_DISABLE_XET=1 HF_HUB_DOWNLOAD_TIMEOUT=60 HF_HUB_ETAG_TIMEOUT=30 \
    timeout 2700 docling-tools models download tableformer \
 && HF_HUB_DISABLE_XET=1 HF_HUB_DOWNLOAD_TIMEOUT=60 HF_HUB_ETAG_TIMEOUT=30 \
    timeout 2700 python -c "\
from pathlib import Path; \
from huggingface_hub import snapshot_download; \
from docling.datamodel.layout_model_specs import DOCLING_LAYOUT_V2 as spec; \
from docling.datamodel.settings import settings as ds; \
target = Path(ds.cache_dir) / 'models' / spec.model_repo_folder; \
snapshot_download(repo_id=spec.repo_id, revision=spec.revision, local_dir=str(target)); \
print('layout-v2 baked into', target)"

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
