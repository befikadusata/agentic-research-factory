# Agentic Research Factory

[![CI](https://github.com/befikadusata/agentic-research-factory/actions/workflows/ci.yml/badge.svg)](https://github.com/befikadusata/agentic-research-factory/actions/workflows/ci.yml)

An AI-powered market research automation platform with **Human-in-the-Loop (HITL) quality control**, hybrid retrieval-augmented generation (RAG), and real-time step streaming. Built for B2B sales teams, product marketers, and founders to compile highly cited, professional dossiers in minutes instead of days.

---

## 🚀 Key Capabilities

* **Dynamic Agent Routing**: Uses a **LangGraph Supervisor** to choreograph specialized CrewAI agents (`Strategist`, `Researcher`, `Analyst`, `Reviewer`, `Writer`, `Editor`) tailored to the selected task profile.
* **Vertical Research Playbooks**: Native playbooks designed for specific domains:
  - 🎯 **B2B Sales Lead Intel**: Target profile dossiers, buyer criteria, and outreach hooks.
  - 📊 **Marketing Competitor Briefs**: Feature audits, pricing analysis, and positioning gaps.
  - 🚀 **Founder Strategy Briefs**: Market segments, ARR validation, and competitor categories.
* **High-Precision Hybrid RAG**: Ingests uploaded PDFs using **LlamaParse**, indexes vectors + keyword counts in **PostgreSQL** (`pgvector`), and re-ranks chunks using an **MS-MARCO Cross-Encoder**.
* **Interactive HITL Checkpoints**: Pauses the agent run at critical stages, streams a draft summary, and lets users inject corrective instructions before synthesis continues.
* **Real-time Console Streaming**: Pipes agent logs and status transitions to the Next.js UI via **Redis Pub/Sub** and **Server-Sent Events (SSE)**.
* **Multi-tenancy**: Tenant workspaces with role-based permissions (`viewer`, `operator`, `admin`).
* **Cost Auditing**: Logs token usage and cost per agent invocation.

---

## 🛠 Technology Stack

### Backend (`/backend`)
* **Framework**: FastAPI + Python 3.11
* **Agent Framework**: LangGraph (supervisor routing) + CrewAI
* **Database**: PostgreSQL (`pgvector`) + SQLAlchemy (asyncpg) + Alembic
* **Real-time / Caching**: Redis (Pub/Sub + task state)
* **Background Worker**: Celery
* **Ingestion**: LlamaParse + LangChain text splitters + SentenceTransformers
* **PDF Export**: WeasyPrint

### Frontend (`/frontend`)
* **Framework**: Next.js 15 (App Router) + React 19
* **Auth**: NextAuth.js (Google OAuth)
* **Styling**: Tailwind CSS

---

## ⚡ Quick Start (Docker)

The fastest way to get a running stack. All services — Next.js, FastAPI, PostgreSQL, Redis, Celery, and pgvector — start with one command. Volumes are mounted for hot-reload: the backend runs with `--reload` and the frontend runs `next dev`.

**1. Configure the backend environment:**
```bash
cp backend/.env.example backend/.env
```
Open `backend/.env` and fill in your API keys. The minimum set to run the full feature suite:

| Key | Where to get it |
| :-- | :-- |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) |
| `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) |
| `TAVILY_API_KEY` | [tavily.com](https://tavily.com) |
| `FIRECRAWL_API_KEY` | [firecrawl.dev](https://www.firecrawl.dev) |
| `LLAMA_CLOUD_API_KEY` | [cloud.llamaindex.ai](https://cloud.llamaindex.ai) |
| `BACKEND_JWT_SECRET` | `openssl rand -hex 32` |
| `NEXTAUTH_SECRET` | `openssl rand -hex 32` |

> Keys marked optional in dev (`TAVILY_API_KEY`, `FIRECRAWL_API_KEY`, `LLAMA_CLOUD_API_KEY`) can be left blank — the server boots with a warning and those features are disabled at call time.

**2. Configure the frontend environment (Docker):**

Open `docker-compose.yml` and replace the placeholder values in the `frontend.environment` block:
```
NEXTAUTH_SECRET     → same value as backend NEXTAUTH_SECRET
GOOGLE_CLIENT_ID    → from Google Cloud Console
GOOGLE_CLIENT_SECRET → from Google Cloud Console
```

**3. Start all services:**
```bash
docker compose up --build
```

Migrations run automatically via the `migrate` init container before the backend starts.

---

## 🌐 Accessing the App

| Service | URL |
| :-- | :-- |
| Frontend | http://localhost:3000 |
| Backend API docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

---

## 🧪 Running Tests

```bash
# Outside Docker
cd backend
uv run pytest -v

# Or inside Docker
docker compose run --rm backend uv run pytest -v
```

Frontend e2e tests:
```bash
cd frontend
npx playwright test
```

---

## 💻 Local Development

For contributors who want to run services directly on the host (faster iteration, easier debugging):

### Prerequisites
- PostgreSQL with `pgvector` extension
- Redis
- Python 3.11+ with [uv](https://docs.astral.sh/uv/)
- Node.js 20+

### Backend
```bash
cd backend
cp .env.example .env         # fill in your keys
uv sync
uv run alembic upgrade head
uv run uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
cp .env.local.example .env.local   # fill in NEXTAUTH vars and GOOGLE OAuth
npm install --legacy-peer-deps
npm run dev
```

---

## 🔑 Environment Variables

### Backend (`backend/.env`)

| Variable | Required in dev | Required in prod | Notes |
| :-- | :--: | :--: | :-- |
| `ENVIRONMENT` | — | — | `development` or `production` (default: `development`) |
| `DATABASE_URL` | ✓ | ✓ | `postgresql+asyncpg://...` |
| `REDIS_URL` | ✓ | ✓ | default: `redis://localhost:6379/0` |
| `BACKEND_JWT_SECRET` | ✓ | ✓ | `openssl rand -hex 32` |
| `NEXTAUTH_SECRET` | ✓ | ✓ | must match frontend |
| `GROQ_API_KEY` | ✓ | ✓ | Strategist + query rewriter |
| `OPENROUTER_API_KEY` | ✓ | ✓ | Analyst / Writer / Editor |
| `GEMINI_API_KEY` | ✓ | ✓ | Embeddings |
| `TAVILY_API_KEY` | optional | ✓ | Web search; warns if missing in dev |
| `FIRECRAWL_API_KEY` | optional | ✓ | Web scraping; warns if missing in dev |
| `LLAMA_CLOUD_API_KEY` | optional | ✓ | PDF parsing; warns if missing in dev |

In `production` mode, missing optional keys cause a hard startup failure with an explicit error message.

### Frontend (`frontend/.env.local`)

| Variable | Notes |
| :-- | :-- |
| `NEXTAUTH_URL` | Full URL of the frontend (e.g. `http://localhost:3000`) |
| `NEXTAUTH_SECRET` | Must match backend `NEXTAUTH_SECRET` |
| `GOOGLE_CLIENT_ID` | Google OAuth app |
| `GOOGLE_CLIENT_SECRET` | Google OAuth app |
| `NEXT_PUBLIC_BACKEND_URL` | Backend base URL (e.g. `http://localhost:8000`) |

---

## 📁 Documentation

| Document | Purpose |
| :-- | :-- |
| 📊 **[Architecture Spec](docs/architecture.md)** | LangGraph supervisor logic, RAG retrieval flow, database models |
| 📦 **[Deployment Guide](docs/deployment.md)** | Railway, Render, Vercel, and Neon deployment instructions |
| 🛡 **[Reliability Guide](docs/reliability.md)** | Graceful degradation, retry mappings, error fallback rules |
| ⚡ **[RAG Optimizations](docs/optimizations.md)** | Text splitting, dual indexing, query expansion, cross-encoder re-ranking |
| 🧪 **[Evaluation Set](docs/evaluation/eval_set.md)** | 20 standardized benchmark topics |
| 📈 **[Evaluation Results](docs/evaluation/eval_results.md)** | Benchmark latency and scorecard tracker |
| 📋 **[Demo Readiness Checklist](docs/checklists/demo_readiness.md)** | Pre-release verification checklist |
