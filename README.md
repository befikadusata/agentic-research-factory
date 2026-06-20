# Agentic Research Factory

[![CI](https://github.com/befikadusata/agentic-research-factory/actions/workflows/ci.yml/badge.svg)](https://github.com/befikadusata/agentic-research-factory/actions/workflows/ci.yml)

An AI-powered market research automation platform with **Human-in-the-Loop (HITL) quality control**, hybrid retrieval-augmented generation (RAG), and real-time step streaming. Built for B2B sales teams, product marketers, and founders to compile highly cited, professional dossiers in minutes instead of days.

---

## 🚀 Key Capabilities

* **Dynamic Agent Routing**: Uses a **LangGraph Supervisor** to choreograph specialized CrewAI agents (`Strategist`, `Researcher`, `Analyst`, `Reviewer`, `Writer`, `Editor`) tailored to the selected task profile.
* **Vertical Research Playbooks**: Native playbooks designed for specific domains:
  - 🎯 **B2B Sales Lead Intel**: Extracts detailed target profile dossier logs, target buyer criteria, and hook hooks.
  - 📊 **Marketing Competitor Briefs**: Conducts feature audits, pricing analysis, and positioning gaps.
  - 🚀 **Founder Strategy Briefs**: Investigates market segments, ARR validation playbooks, and competitor categories.
* **High-Precision Hybrid RAG**: Ingests uploaded PDFs using **LlamaParse**, splits text recursively, indexes document vectors alongside keyword counts in **PostgreSQL** (`pgvector`), expands query semantics, and re-ranks candidate chunks using an **MS-MARCO Cross-Encoder**.
* **Interactive Human-in-the-Loop Checkpoints**: Pauses the agent run at critical stages (e.g. after compiling research) and streams draft summaries. Users can write corrective feedback prompts directly into the running agent graph before it moves to synthesis.
* **Real-time Console Streaming**: Pipes active agent logs, reasoning paths, and status transitions directly to the Next.js UI using **Redis Pub/Sub** and **Server-Sent Events (SSE)**.
* **Resource Isolation & Multi-tenancy**: Features tenant workspaces and role-based permissions (`viewer`, `operator`, `admin`).
* **Cost Auditing**: Logs token usage metrics and financial costs per agent invocation to monitor compute overhead.

---

## 🛠 Technology Stack

### Backend API (`/backend`)
* **Framework**: FastAPI (async event loops) + Python 3.11
* **Agent Framework**: LangGraph (supervisor routing) + CrewAI
* **Database**: PostgreSQL (`pgvector` integration) + SQLAlchemy (asyncpg) + Alembic Migrations
* **Real-time / Caching**: Redis (Pub/Sub signaling & task state management)
* **Background Worker**: Celery (task queue orchestration)
* **Ingestion & Processing**: LlamaParse (PDF-to-markdown) + LangChain text splitters + SentenceTransformers
* **PDF Exporter**: WeasyPrint (HTML-to-PDF formatting engine)

### Frontend Dashboard (`/frontend`)
* **Framework**: Next.js 15 (App Router) + React 19
* **Authentication**: NextAuth.js (Google OAuth configuration)
* **Styling**: Tailwind CSS (dark mode theme)

---

## 📁 Documentation Map

We maintain detailed system guides under the [docs/](file:///home/befikadusata/Devs/2026/agentic-research-factory/docs) directory:

| Document | Purpose |
| :--- | :--- |
| 📊 **[Architecture Spec](file:///home/befikadusata/Devs/2026/agentic-research-factory/docs/architecture.md)** | Deep dive into LangGraph supervisor logic, RAG retrieval flow, and database models. |
| 📦 **[Deployment Guide](file:///home/befikadusata/Devs/2026/agentic-research-factory/docs/deployment.md)** | Complete environment setup instructions for Railway/Render, Vercel, and Neon database deployments. |
| 🛡 **[Reliability Guide](file:///home/befikadusata/Devs/2026/agentic-research-factory/docs/reliability.md)** | Graceful degradation policies, tenacity retry mappings, and api error fallback rules. |
| ⚡ **[RAG Optimizations](file:///home/befikadusata/Devs/2026/agentic-research-factory/docs/optimizations.md)** | Explanation of recursive character text splitters, dual indexing, query expansion, and cross-encoder re-ranking. |
| 🧪 **[Evaluation Set](file:///home/befikadusata/Devs/2026/agentic-research-factory/docs/evaluation/eval_set.md)** | Benchmark set containing 20 standardized topics to evaluate agent accuracy, depth, and citation metrics. |
| 📈 **[Evaluation Results](file:///home/befikadusata/Devs/2026/agentic-research-factory/docs/evaluation/eval_results.md)** | Template tracker for benchmark run latencies and model judgment scorecard metrics. |
| 📋 **[Demo Readiness Checklist](file:///home/befikadusata/Devs/2026/agentic-research-factory/docs/checklists/demo_readiness.md)** | Step-by-step checklist to verify features locally and in staging before product release. |
| 💼 **[Portfolio Folder](file:///home/befikadusata/Devs/2026/agentic-research-factory/docs/portfolio)** | Client-facing case studies, freelancing portfolio write-ups, FAQs, and Loom script details. |

---

## ⚡ Quick Start

### Method A: Docker Compose (All-in-One Setup)
The quickest way to run the entire infrastructure stack (Next.js, FastAPI, PostgreSQL, Redis, Celery, and pgvector):

1. **Clone & Configure**:
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env to include your LLM, Tavily, and Firecrawl API keys.
   ```
2. **Start Services**:
   ```bash
   docker compose up --build
   ```
3. **Access Application**:
   * Frontend: `http://localhost:3000`
   * Backend Swagger API: `http://localhost:8000/docs`
   * Redis Broker: `http://localhost:6379`

---

### Method B: Manual Local Development

#### 1. Database (PostgreSQL + Redis)
Ensure you have running instances of PostgreSQL (with `pgvector` enabled) and a Redis server locally.

#### 2. Backend Setup
1. Navigate to the backend directory and synchronize dependencies:
   ```bash
   cd backend
   uv sync
   ```
2. Create and fill in environment variables:
   ```bash
   cp .env.example .env
   # Fill in DATABASE_URL, LLM_API_KEY, TAVILY_API_KEY, FIRECRAWL_API_KEY, and LLAMA_CLOUD_API_KEY.
   ```
3. Apply database migrations:
   ```bash
   uv run alembic upgrade head
   ```
4. Boot the FastAPI server:
   ```bash
   uv run uvicorn main:app --reload
   ```

#### 3. Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd ../frontend
   npm install
   ```
2. Configure environmental settings:
   ```bash
   cp .env.local.example .env.local
   # Ensure NEXT_PUBLIC_BACKEND_URL points to your running FastAPI backend (default: http://localhost:8000)
   ```
3. Start the Next.js development server:
   ```bash
   npm run dev
   ```

---

## 🧪 Running Tests

### Backend Unit & Integration Tests
The backend test suite covers authentication routes, verticals validation, Redis signaling, and SSE streaming log loops.
```bash
cd backend
uv run pytest -v
```

### Frontend End-to-End Tests
Playwright config files are provided to run automated flows:
```bash
cd frontend
npx playwright test
```
