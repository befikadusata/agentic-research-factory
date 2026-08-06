# Design Decisions

Where the shipped system deliberately diverges from the obvious choice, and what
was left unbuilt on purpose. Everything here is a decision the code can show but
not explain; for how the system works, read the
[architecture specification](architecture.md).

---

## Embeddings live on the application's own PostgreSQL

The straightforward path for document RAG is a dedicated vector service — Chroma
locally, a hosted vector database in production. This project uses
[`vecs`](https://github.com/supabase/vecs) against pgvector in a `vecs` schema on
the *same* PostgreSQL instance the application already runs.

The reason is setup cost. Compose already runs `pgvector/pgvector:pg16` for
application data, so there is no second service to provision, no second backup
story, and no extra container for someone evaluating the project. `VECTOR_DB_URL`
still exists for anyone who wants the embeddings elsewhere — point it at Supabase,
a separate database, or a managed pgvector instance and nothing else changes.

Left unset, `config.py` derives it from `DATABASE_URL` by stripping the async
driver: SQLAlchemy needs `postgresql+asyncpg://` and `vecs` uses psycopg2, which
needs a bare `postgresql://`. That translation is the only reason the two settings
are not simply the same string.

`SUPABASE_DB_URL` is honoured as a deprecated alias — it is copied into
`VECTOR_DB_URL` with a warning rather than ignored silently, because a vector store
that quietly falls back to the wrong database looks like a retrieval-quality
problem, not a configuration one.

## Model selection is capability-based, not a model name

`LLM_MODEL` is unset by default. When it is set it overrides everything and
collapses every agent onto one model, which is useful for a controlled comparison
and wrong for normal operation — a reviewer scoring a rubric and a writer producing
prose do not want the same model. Per-agent routing resolves each role against the
capabilities the configured providers actually offer, so a single `GROQ_API_KEY` is
enough to run the whole pipeline with different models per role.

## The hybrid retrieval pipeline is kept for abstention, not for ranking

On the evaluation corpus, naive dense top-k *outranks* the full hybrid + re-ranking
pipeline. The pipeline is kept anyway, because the cross-encoder is what makes an
abstention gate possible and dense similarity alone answers every unanswerable
query with a confident-looking fabrication.

This is measured, and the reasoning — including what the harness can and cannot
settle — is in [RAG optimizations](optimizations.md).

## Human approval ends the Celery task rather than blocking it

Waiting for a human inside a running task is simpler to write and holds a worker
for as long as the reviewer takes lunch. A run is instead split into four Celery
tasks — start, analyse, write, finalize — with a gate between each. At a gate the
backend persists the output, sets the awaiting status, and returns the worker slot.

The cost is that a run resumed in a fresh worker process cannot use the graph's
in-memory checkpoint, so `run_service` rebuilds state from the database and sets
`_resume_from` to re-enter at the right node. See [architecture](architecture.md)
§5.

## Deliberately not built

- **Publisher agent.** Scheduled posting to LinkedIn or Buffer after approval. It
  is integration work rather than research work, and it would put OAuth credentials
  for someone's social accounts inside a research tool.
- **Billing and rate limiting.** Out of scope for a system whose interesting
  problem is orchestration.
