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
# exporting the lock keeps the image identical to the tested dev environment.
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project --no-hashes -o /tmp/requirements.txt && \
    uv pip install --system --no-cache -r /tmp/requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
