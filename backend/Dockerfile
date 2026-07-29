FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# WeasyPrint system deps + curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi-dev libcairo2 libpangocairo-1.0-0 \
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

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
