# Deployment Guide

## Architecture

```
┌────────────────┐     ┌──────────────────────┐     ┌───────────────┐
│  Vercel         │────▶│  Railway / Render     │────▶│  Postgres     │
│  (Next.js SSR) │     │  (FastAPI + Uvicorn) │     │  (pgvector)   │
└────────────────┘     └──────────────────────┘     └───────────────┘
     Frontend               Backend                   Database
```

---

## Prerequisites

- [Vercel](https://vercel.com) account
- [Railway](https://railway.app) or [Render](https://render.com) account
- Managed PostgreSQL with pgvector extension (Railway Postgres, Supabase, or Neon)

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
| `LLM_MODEL` | Optional legacy override for every agent |
| `GROQ_API_KEY` | Your Groq API key |
| `OPENROUTER_API_KEY` | Your OpenRouter API key |
| `GEMINI_API_KEY` | Your Google AI Studio key |
| `STRATEGIST_MODEL` | `groq/llama-3.1-8b-instant` |
| `RESEARCHER_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` |
| `ANALYST_MODEL` | `openrouter/free` |
| `WRITER_MODEL` | `openrouter/free` |
| `EDITOR_MODEL` | `openrouter/free` |
| `REVIEWER_MODEL` | `openrouter/free` |
| `QUERY_REWRITER_MODEL` | `groq/llama-3.1-8b-instant` |
| `EVAL_MODEL` | `openrouter/free` |
| `EMBEDDING_MODEL` | `gemini-embedding-2` |
| `TAVILY_API_KEY` | Your Tavily API key |
| `FIRECRAWL_API_KEY` | Your Firecrawl API key |
| `LLAMA_CLOUD_API_KEY` | Your LlamaParse API key |
| `BACKEND_JWT_SECRET` | A random 32+ char secret |
| `NEXTAUTH_SECRET` | Same value as frontend `NEXTAUTH_SECRET` |
| `FRONTEND_URL` | `https://your-app.vercel.app` |

5. Deploy. Verify `GET /health` returns `{"status": "ok"}`.

> **Note:** Setting `ENVIRONMENT=production` enables fail-fast startup. The backend will refuse to start if `TAVILY_API_KEY`, `FIRECRAWL_API_KEY`, or `LLAMA_CLOUD_API_KEY` are missing, logging an explicit error listing the absent keys.

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
| `NEXTAUTH_SECRET` | Same value as backend `NEXTAUTH_SECRET` |
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
| `NEXTAUTH_SECRET` | Invalidates all NextAuth sessions | Update in both, redeploy both |
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
