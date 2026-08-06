# Deployment Guide

## Architecture

```
┌────────────────┐     ┌──────────────────────┐     ┌───────────────┐
│  Vercel         │────▶│  Railway / Render     │────▶│  Postgres     │
│  (Next.js SSR) │     │  (FastAPI + Uvicorn) │     │  (pgvector)   │
└────────────────┘     └──────────────────────┘     └───────────────┘
     Frontend               Backend                   Database
                                │                          ▲
                                ▼                          │
                        ┌───────────────┐          ┌───────────────┐
                        │  S3 / R2 /    │◀─────────│  Celery       │
                        │  MinIO        │          │  worker       │
                        └───────────────┘          └───────────────┘
                        Uploaded PDFs
```

The API and the Celery worker are separate processes that do not share a
filesystem, so uploaded PDFs go to object storage that both can reach.

---

## Prerequisites

- [Vercel](https://vercel.com) account
- [Railway](https://railway.app) or [Render](https://render.com) account
- Managed PostgreSQL with pgvector extension (Railway Postgres, Supabase, or Neon)
- An S3-compatible bucket for uploaded PDFs (AWS S3, Cloudflare R2, DigitalOcean Spaces, or self-hosted MinIO)

---

## Step 1: Provision Database

### Railway Postgres
1. Create a new project → Add PostgreSQL service.
2. Note the connection string from the **Variables** tab.
3. Ensure pgvector is available (Railway Postgres 16 includes it).

### Alternative: Supabase / Neon
1. Create a new project, enable pgvector extension.
2. Copy the `postgresql+asyncpg://` connection string.

---

## Step 2: Deploy Backend (Railway)

1. Create a new Railway service → Connect your GitHub repo.
2. Set the **Root Directory** to `backend`.
3. Set the **Start Command** to:
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
4. Add environment variables:

| Variable | Value |
|----------|-------|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `REDIS_URL` | `redis://host:6379/0` — the Celery broker and the SSE Pub/Sub bus; the API will not pass its own health check without it |
| `GROQ_API_KEY` | Your Groq API key |
| `OPENROUTER_API_KEY` | Your OpenRouter API key |
| `GEMINI_API_KEY` | Your Google AI Studio key — embeddings only; Gemini is deliberately not a routing citizen |
| `EMBEDDING_MODEL` | `gemini-embedding-2` |
| `TAVILY_API_KEY` | Your Tavily API key |
| `FIRECRAWL_API_KEY` | Your Firecrawl API key |
| `LLAMA_CLOUD_API_KEY` | Your LlamaParse API key |
| `BACKEND_JWT_SECRET` | `openssl rand -hex 32` — same value as frontend `BACKEND_JWT_SECRET` |
| `FRONTEND_URL` | `https://your-app.vercel.app` |
| `STORAGE_BACKEND` | `s3` — see the note below |
| `STORAGE_BUCKET` | Bucket for uploaded PDFs |
| `STORAGE_ENDPOINT_URL` | Blank for AWS S3; set for R2, Spaces, or self-hosted MinIO |
| `STORAGE_ACCESS_KEY` | Blank to use an instance/task IAM role instead |
| `STORAGE_SECRET_KEY` | Blank to use an instance/task IAM role instead |
| `STORAGE_REGION` | e.g. `us-east-1` |
| `VECTOR_DB_URL` | Optional. Defaults to `DATABASE_URL` with the async driver stripped, so the application database also serves the `vecs` collections. Set it only to point embeddings at a different Postgres, which must have the `vector` extension |

**Leave every model variable blank.** With `LLM_MODEL` unset, [`services/llm_router.py`](../backend/services/llm_router.py) selects each agent's model from its declared capability (`light`, `reasoning`, `writing`, `tool_use`, `judge`) against `MODEL_REGISTRY`, using whichever provider keys are present. Per-role tiering works on a single provider's keys.

Set one only to deviate from that:

| Variable | Effect |
|----------|--------|
| `LLM_MODEL` | Legacy single-provider mode. If set, every non-judge agent uses this one model and capability routing is bypassed entirely |
| `JUDGE_MODEL` | Pins the reviewer and the eval-confidence judge to a model distinct from the generators they grade, so a model does not grade its own output. Applies in legacy mode too |
| `STRATEGIST_MODEL`, `RESEARCHER_MODEL`, `LEAD_INTEL_MODEL`, `ANALYST_MODEL`, `WRITER_MODEL`, `EDITOR_MODEL`, `REVIEWER_MODEL`, `QUERY_REWRITER_MODEL`, `EVAL_MODEL` | Pin one role to one model slug. The value must be a litellm-resolvable slug; use one of the keys in `MODEL_REGISTRY` unless you have also added pricing for it |

`NEXTAUTH_SECRET` is a frontend-only variable; the backend never reads it.

> **`STORAGE_BACKEND` must be `s3` here.** The API stores an uploaded PDF and a
> Celery worker parses it afterwards, in a separate service with its own
> filesystem. The default `local` writes to a path only the API can see, so the
> worker finds nothing and every upload fails — reported as a PDF with no
> extractable text, since the fetch failure is invisible to the parser. The same
> applies to any managed host that restarts containers, where local disk is
> ephemeral even within one service. Set the same five `STORAGE_*` values on the
> worker service in Step 2b.

5. Deploy. Verify `GET /health` returns `{"status": "ok"}`.

> **Note:** Setting `ENVIRONMENT=production` enables fail-fast startup. The backend refuses to start if `TAVILY_API_KEY`, `FIRECRAWL_API_KEY`, or `LLAMA_CLOUD_API_KEY` are missing, logging an explicit error listing the absent keys. It also refuses to start if `BACKEND_JWT_SECRET` is still one of the development values the repo ships, or is shorter than 32 characters.

---

## Step 2b: Deploy Celery Worker

The API only enqueues work. Without a worker, runs are created and then sit in `pending` forever, and uploaded PDFs are never parsed — with no error surfaced anywhere.

1. Create a second Railway service from the same repo, **Root Directory** `backend`.
2. Set the **Start Command** to:
   ```
   celery -A celery_app worker --loglevel=info --concurrency=1 -Q default
   ```
   `-Q default` is required. [`celery_app.py`](../backend/celery_app.py) routes every task — `execute_run_task`, `ingest_doc_task`, `dispatch_due_monitors_task`, `reap_orphaned_runs_task` — to the `default` queue, so a worker left on Celery's built-in `celery` queue consumes nothing and fails silently.
3. Give it **the same environment variables as Step 2**, including all five `STORAGE_*` values. The worker reads back exactly what the API wrote, so any divergence in bucket, endpoint, or credentials breaks uploads.

Scale by running more worker services or raising `--concurrency`. Note that `worker_max_tasks_per_child=1` recycles the child process after every task, so each task starts with a clean event loop; this is deliberate and should not be removed.

---

## Step 2c: Deploy Celery Beat

Beat is only required if you use scheduled monitors or want orphaned runs reaped automatically.

1. Create a third service from the same repo, **Root Directory** `backend`, same environment variables.
2. Set the **Start Command** to:
   ```
   celery -A celery_app beat --loglevel=info --schedule=/tmp/celerybeat-schedule
   ```

**Run exactly one beat instance.** Beat is a scheduler, not a worker: two instances mean every scheduled monitor fires twice and bills twice. It dispatches `dispatch_due_monitors_task` every 60s and `reap_orphaned_runs_task` every 300s; the runs those spawn execute on the Step 2b worker, not in beat itself.

---

## Step 3: Deploy Frontend (Vercel)

1. Import your GitHub repo in Vercel.
2. Set the **Root Directory** to `frontend`.
3. Set the **Framework Preset** to `Next.js`.
4. Add environment variables:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_BACKEND_URL` | `https://your-backend.railway.app` |
| `NEXTAUTH_URL` | `https://your-app.vercel.app` |
| `NEXTAUTH_SECRET` | `openssl rand -hex 32` — frontend only, unrelated to the backend |
| `BACKEND_JWT_SECRET` | Same value as backend `BACKEND_JWT_SECRET` (a mismatch 401s every API call) |
| `GOOGLE_CLIENT_ID` | Your Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Your Google OAuth client secret |

5. Deploy. Verify the app loads at the Vercel URL.

---

## Step 4: Post-Deploy Verification

Run through the full happy path:

1. **Sign in** via Google OAuth.
2. **Create a new run** → select a vertical → fill inputs → submit.
3. **Verify SSE stream** — agent logs appear in real time.
4. **HITL checkpoint** — approve the research summary.
5. **Output delivery** — download PDF and MD.
6. **Dashboard** — verify the run appears in the runs list.

---

## Step 5: Production CORS

Ensure `FRONTEND_URL` in the backend matches the exact Vercel domain. The backend CORS middleware only allows requests from this origin.

---

## Secret Rotation Checklist

| Secret | Rotation Impact | Steps |
|--------|----------------|-------|
| `BACKEND_JWT_SECRET` | Invalidates all active sessions | Update in both backend + frontend env vars, redeploy both |
| `NEXTAUTH_SECRET` | Invalidates all NextAuth sessions | Update in the frontend, redeploy frontend |
| `GROQ_API_KEY` | Interrupts Groq-backed agents | Update backend env var, redeploy backend |
| `OPENROUTER_API_KEY` | Interrupts OpenRouter-backed agents | Update backend env var, redeploy backend |
| `GEMINI_API_KEY` | Interrupts Gemini embeddings | Update backend env var, redeploy backend |
| `TAVILY_API_KEY` | Search degradation until updated | Update backend, redeploy |
| `FIRECRAWL_API_KEY` | Scraping degradation until updated | Update backend, redeploy |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| CORS errors in browser | Verify `FRONTEND_URL` matches the Vercel domain exactly (no trailing slash) |
| 500 on `/runs` | Check `DATABASE_URL` is reachable and pgvector is enabled |
| SSE stream disconnects | Check Railway/Render doesn't have a request timeout < 30 min |
| OAuth callback fails | Verify `NEXTAUTH_URL` matches the deployed domain |
| Every uploaded PDF fails as "no text could be extracted" | The worker cannot fetch what the API stored. Confirm `STORAGE_BACKEND=s3` and that the identical `STORAGE_*` values are set on **both** the API and the worker. A genuinely unparseable PDF fails for some uploads; a storage fault fails for all of them |
| "The uploaded file is no longer in storage" | The bucket, key prefix, or credentials differ between the API and the worker, or the object was deleted out from under the row |
