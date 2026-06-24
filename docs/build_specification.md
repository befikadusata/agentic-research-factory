# Agentic Research Factory — Complete Build Specification
> **For AI Agent Use.** This document is a self-contained, step-by-step build spec. Follow every section in order. Do not skip sections. Do not infer missing details — all decisions are explicit here.

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Monorepo Structure](#2-monorepo-structure)
3. [Environment Variables](#3-environment-variables)
4. [Backend — FastAPI](#4-backend--fastapi)
5. [Agents — CrewAI](#5-agents--crewai)
6. [Tools — Tavily, Firecrawl, RAG](#6-tools--tavily-firecrawl-rag)
7. [HITL — Human-in-the-Loop](#7-hitl--human-in-the-loop)
8. [Output Formatters](#8-output-formatters)
9. [Database — PostgreSQL](#9-database--postgresql)
10. [Frontend — Next.js 15](#10-frontend--nextjs-15)
11. [Authentication — NextAuth](#11-authentication--nextauth)
12. [Streaming — SSE](#12-streaming--sse)
13. [API Routes Reference](#13-api-routes-reference)
14. [V2 Extensions](#14-v2-extensions)
15. [Deployment](#15-deployment)
16. [Testing Checklist](#16-testing-checklist)

---

## 1. Project Overview

### What This System Does
Takes a user-supplied topic or company name, autonomously researches it using live web search and document retrieval, pauses for human approval, then generates polished content in three formats. All agent steps stream to the UI in real time.

### Target Vertical
AI Market Research & Content Pipeline. Demo topic: **"Competitive landscape for Notion in project management, 2025"**.

### V1 Scope (build this first)
- 5 agents: Researcher, Analyst, Writer, Editor, RAG Retriever (simplified)
- 1 HITL checkpoint (after research, before writing)
- 3 output formats: Full Research Report, LinkedIn Article, Executive Summary
- PDF + Markdown download
- Google OAuth via NextAuth
- Session history (last 10 runs per user)
- SSE streaming of agent steps
- Responsive UI, dark mode

### Non-Goals for V1 (do NOT build)
- Persistent vector DB across sessions
- LangGraph Supervisor
- LLM-as-Judge eval scores
- Twitter thread / Google Doc / newsletter formats
- Multi-user workspaces
- Stripe billing
- Docker Compose
- Rate limiting

---

## 2. Monorepo Structure

```
agent-research-factory/
├── backend/
│   ├── main.py                  # FastAPI app entrypoint
│   ├── config.py                # Settings via pydantic-settings
│   ├── database.py              # SQLAlchemy engine + session
│   ├── models.py                # ORM models
│   ├── schemas.py               # Pydantic request/response schemas
│   ├── routers/
│   │   ├── runs.py              # POST /runs, GET /runs
│   │   ├── stream.py            # GET /runs/{id}/stream  (SSE)
│   │   ├── hitl.py              # POST /runs/{id}/approve
│   │   ├── upload.py            # POST /upload
│   │   └── outputs.py          # GET /runs/{id}/output/{format}
│   ├── agents/
│   │   ├── crew.py              # CrewAI crew definition
│   │   ├── researcher.py        # Researcher agent + task
│   │   ├── analyst.py           # Analyst agent + task
│   │   ├── writer.py            # Writer agent + task
│   │   └── editor.py            # Editor agent + task
│   ├── tools/
│   │   ├── search.py            # Tavily search tool
│   │   ├── scraper.py           # Firecrawl tool
│   │   └── rag.py               # Chroma in-memory RAG tool
│   ├── formatters/
│   │   ├── report.py            # Full research report formatter
│   │   ├── linkedin.py          # LinkedIn article formatter
│   │   └── summary.py           # Executive summary formatter
│   ├── services/
│   │   ├── run_service.py       # Orchestrates crew + HITL + DB
│   │   └── pdf_service.py       # Markdown → PDF conversion
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx             # Dashboard (run history)
│   │   ├── new/
│   │   │   └── page.tsx         # New run form
│   │   ├── runs/
│   │   │   └── [id]/
│   │   │       └── page.tsx     # Run detail + streaming + HITL + output
│   │   └── api/
│   │       └── auth/
│   │           └── [...nextauth]/
│   │               └── route.ts
│   ├── components/
│   │   ├── AgentLog.tsx         # Streaming log panel
│   │   ├── HitlModal.tsx        # HITL approval modal
│   │   ├── OutputPanel.tsx      # Tabbed output viewer
│   │   ├── FormatSelector.tsx   # Report / LinkedIn / Summary picker
│   │   ├── FileUpload.tsx       # PDF drag-and-drop uploader
│   │   ├── RunCard.tsx          # History card
│   │   └── DownloadButton.tsx   # PDF / MD download
│   ├── lib/
│   │   ├── api.ts               # Typed API client
│   │   ├── auth.ts              # NextAuth config
│   │   └── types.ts             # Shared TypeScript types
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── package.json
│   └── .env.local.example
├── .gitignore
└── README.md
```

---

## 3. Environment Variables

### Backend — `backend/.env`
```env
# LLM
LLM_PROVIDER=openai-compatible
LLM_MODEL=
LLM_API_KEY=
LLM_BASE_URL=
GROQ_API_KEY=your-groq-key
OPENROUTER_API_KEY=your-openrouter-key
GEMINI_API_KEY=your-gemini-key
STRATEGIST_MODEL=groq/llama-3.1-8b-instant
RESEARCHER_MODEL=meta-llama/llama-3.3-70b-instruct:free
LEAD_INTEL_MODEL=meta-llama/llama-3.3-70b-instruct:free
QUERY_REWRITER_MODEL=groq/llama-3.1-8b-instant
ANALYST_MODEL=openrouter/free
WRITER_MODEL=openrouter/free
EDITOR_MODEL=openrouter/free
REVIEWER_MODEL=openrouter/free
EVAL_MODEL=openrouter/free
EMBEDDING_MODEL=gemini-embedding-2

# Search & Scraping
TAVILY_API_KEY=tvly-...
FIRECRAWL_API_KEY=fc-...

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/research_factory

# App
BACKEND_JWT_SECRET=generate-with-openssl-rand-hex-32
NEXTAUTH_SECRET=generate-with-openssl-rand-hex-32
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000

# PDF Parsing
LLAMA_CLOUD_API_KEY=llx-...

# Optional — leave blank for V1
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

### Frontend — `frontend/.env.local`
```env
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=generate-with-openssl-rand-hex-32
BACKEND_JWT_SECRET=generate-with-openssl-rand-hex-32

GOOGLE_CLIENT_ID=...apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=...

NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

---

## 4. Backend — FastAPI

### `backend/requirements.txt`
```
fastapi==0.115.0
uvicorn[standard]==0.30.6
python-dotenv==1.0.1
pydantic-settings==2.5.2
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.13.3
crewai==0.80.0
crewai-tools==0.14.0
PyJWT==2.9.0
tavily-python==0.5.0
firecrawl-py==1.5.0
chromadb==0.5.23
llama-parse==0.5.14
litellm==1.51.0
langchain-community==0.3.8
sse-starlette==2.1.3
python-multipart==0.0.12
weasyprint==62.3
markdown==3.7
```

### `backend/main.py`
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import init_db
from routers import runs, stream, hitl, upload, outputs
from config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="Agentic Research Factory", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs.router, prefix="/runs", tags=["runs"])
app.include_router(stream.router, prefix="/runs", tags=["stream"])
app.include_router(hitl.router, prefix="/runs", tags=["hitl"])
app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(outputs.router, prefix="/runs", tags=["outputs"])

@app.get("/health")
async def health():
    return {"status": "ok"}
```

### `backend/config.py`
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    LLM_PROVIDER: str = "openai-compatible"
    LLM_MODEL: str
    LLM_API_KEY: str
    LLM_BASE_URL: str | None = None
    TAVILY_API_KEY: str
    FIRECRAWL_API_KEY: str
    LLAMA_CLOUD_API_KEY: str
    DATABASE_URL: str
    BACKEND_JWT_SECRET: str
    NEXTAUTH_SECRET: str
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"

    class Config:
        env_file = ".env"

settings = Settings()
```

### `backend/database.py`
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

### `backend/models.py`
```python
from sqlalchemy import Column, String, DateTime, Text, Enum as SAEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid, enum
from datetime import datetime, timezone
from database import Base

class RunStatus(str, enum.Enum):
    pending    = "pending"
    researching = "researching"
    awaiting_hitl = "awaiting_hitl"
    writing    = "writing"
    complete   = "complete"
    failed     = "failed"

class Run(Base):
    __tablename__ = "runs"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(String, nullable=False, index=True)
    topic      = Column(Text, nullable=False)
    format     = Column(String, nullable=False)  # "report" | "linkedin" | "summary"
    status     = Column(SAEnum(RunStatus), default=RunStatus.pending, nullable=False)
    doc_paths  = Column(JSON, default=list)       # uploaded PDF paths
    research_output = Column(Text)               # raw research markdown
    final_output    = Column(Text)               # final formatted content
    logs       = Column(JSON, default=list)       # list of {agent, message, ts}
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
```

### `backend/schemas.py`
```python
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from models import RunStatus
from typing import Optional

class CreateRunRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500)
    format: str = Field(..., pattern="^(report|linkedin|summary)$")
    doc_ids: list[str] = Field(default_factory=list)

class HitlApproveRequest(BaseModel):
    instruction: Optional[str] = None   # optional redirect instruction from user

class RunResponse(BaseModel):
    id: UUID
    topic: str
    format: str
    status: RunStatus
    created_at: datetime

    class Config:
        from_attributes = True

class RunDetailResponse(RunResponse):
    logs: list[dict]
    research_output: Optional[str]
    final_output: Optional[str]
```

---

## 5. Agents — CrewAI

### Agent Design Rules
- In routed mode, each agent resolves its own model from config so providers can be split by stage without code changes.
- Every agent has `verbose=True` so step output is capturable for SSE streaming.
- Tasks use `async_execution=False` — sequential, not parallel (V1).
- The crew runs in `Process.sequential` mode.

### `backend/agents/crew.py`
```python
from crewai import Crew, Process
from agents.researcher import researcher_agent, research_task
from agents.analyst import analyst_agent, analysis_task
from agents.writer import writer_agent, write_task
from agents.editor import editor_agent, edit_task
from typing import Callable, Optional
import asyncio

def build_crew(
    topic: str,
    output_format: str,
    context_docs: str = "",
    step_callback: Optional[Callable] = None,
) -> Crew:
    """
    Build and return a configured CrewAI crew.
    step_callback(agent_name: str, output: str) is called after each task.
    """
    researcher = researcher_agent()
    analyst    = analyst_agent()
    writer     = writer_agent()
    editor     = editor_agent()

    r_task = research_task(researcher, topic, context_docs)
    a_task = analysis_task(analyst, topic)
    w_task = write_task(writer, topic, output_format)
    e_task = edit_task(editor, topic)

    crew = Crew(
        agents=[researcher, analyst, writer, editor],
        tasks=[r_task, a_task, w_task, e_task],
        process=Process.sequential,
        verbose=True,
        step_callback=step_callback,
    )
    return crew
```

### `backend/agents/researcher.py`
```python
from crewai import Agent, Task
from tools.search import tavily_search_tool
from tools.scraper import firecrawl_tool
from tools.rag import rag_tool
from config import settings

def researcher_agent() -> Agent:
    return Agent(
        role="Senior Research Analyst",
        goal="Gather comprehensive, accurate, and current information on the given topic using web search, page scraping, and uploaded documents.",
        backstory=(
            "You are an expert research analyst with 15 years of experience in market intelligence. "
            "You never fabricate data. You cite every source. You prioritise primary sources over aggregators. "
            "You know when to stop searching and synthesise what you have."
        ),
        tools=[tavily_search_tool, firecrawl_tool, rag_tool],
        llm=settings.LLM_MODEL,
        verbose=True,
        max_iter=8,
    )

def research_task(agent: Agent, topic: str, context_docs: str) -> Task:
    context_section = f"\n\nRelevant excerpts from uploaded documents:\n{context_docs}" if context_docs else ""
    return Task(
        description=f"""
Research the following topic thoroughly: **{topic}**

Steps:
1. Use Tavily to search for 5–8 highly relevant articles, reports, or data sources.
2. For the 3 most valuable URLs, use Firecrawl to scrape the full page content.
3. If context documents are provided, query them using the RAG tool.
4. Synthesise all findings into a structured research summary.

Output format (strict):
## Research Summary: {topic}

### Key Findings
- [finding 1 with source URL]
- [finding 2 with source URL]
...

### Data & Statistics
- [stat 1 — source]
...

### Sources
1. [Title](URL)
2. [Title](URL)
...
{context_section}
""",
        expected_output="A structured research summary with key findings, statistics, and cited sources in Markdown format.",
        agent=agent,
    )
```

### `backend/agents/analyst.py`
```python
from crewai import Agent, Task
from config import settings

def analyst_agent() -> Agent:
    return Agent(
        role="Strategic Insights Analyst",
        goal="Extract actionable insights, trends, competitive gaps, and strategic implications from raw research.",
        backstory=(
            "You are a McKinsey-trained analyst who transforms raw data into strategic narratives. "
            "You identify patterns others miss. You always ask: so what does this mean, and what should be done?"
        ),
        tools=[],
        llm=settings.LLM_MODEL,
        verbose=True,
        max_iter=4,
    )

def analysis_task(agent: Agent, topic: str) -> Task:
    return Task(
        description=f"""
Using the research summary from the previous task, extract strategic insights on: **{topic}**

Output format (strict):
## Strategic Analysis: {topic}

### Top 3 Trends
1. [trend — evidence — implication]
2. ...
3. ...

### Competitive Gaps & Opportunities
- [gap 1]
- [gap 2]

### Key Risks
- [risk 1]

### Recommended Angles for Content
- [angle 1 — why it resonates with the target audience]
- [angle 2]
""",
        expected_output="A strategic analysis with trends, gaps, risks, and content angles in Markdown format.",
        agent=agent,
        context=[],  # populated by CrewAI from previous task output
    )
```

### `backend/agents/writer.py`
```python
from crewai import Agent, Task
from config import settings

FORMAT_INSTRUCTIONS = {
    "report": """
Write a full research report (1,500–2,500 words) with these sections:
- Executive Summary (150 words)
- Introduction & Context
- Key Findings (with sub-sections per theme)
- Data & Statistics (use a markdown table)
- Strategic Implications
- Recommendations
- Conclusion
- References (cite all sources from research)
""",
    "linkedin": """
Write a LinkedIn article (1,200–1,500 words) with:
- A strong hook opening (2–3 sentences, bold claim or surprising stat)
- 4–5 insight sections with short headers
- Concrete examples and data points
- A closing call-to-action paragraph
- Professional but conversational tone
- NO hashtags in the body (add 3–5 at the very end)
""",
    "summary": """
Write a one-page executive summary (400–600 words) with:
- Title
- Situation (2–3 sentences of context)
- Key Findings (5 bullet points max)
- Strategic Implications (3 bullet points)
- Recommended Next Steps (3 action items)
Use concise, business-appropriate language.
""",
}

def writer_agent() -> Agent:
    return Agent(
        role="Senior Content Writer",
        goal="Transform research and analysis into polished, publication-ready content that matches the requested format perfectly.",
        backstory=(
            "You are a former Wall Street Journal journalist turned content strategist. "
            "You write clearly, cite evidence, avoid filler phrases, and always put the most interesting "
            "point first. You adapt your voice perfectly to the requested format."
        ),
        tools=[],
        llm=settings.LLM_MODEL,
        verbose=True,
        max_iter=3,
    )

def write_task(agent: Agent, topic: str, output_format: str) -> Task:
    instructions = FORMAT_INSTRUCTIONS.get(output_format, FORMAT_INSTRUCTIONS["report"])
    return Task(
        description=f"""
Using the research summary and strategic analysis from previous tasks, write content about: **{topic}**

Format instructions:
{instructions}

Rules:
- Ground every claim in the research. No fabricated statistics.
- Use plain Markdown (no HTML).
- Start the document with a single H1 title.
""",
        expected_output=f"A complete, publication-ready {output_format} in Markdown format.",
        agent=agent,
    )
```

### `backend/agents/editor.py`
```python
from crewai import Agent, Task
from config import settings

def editor_agent() -> Agent:
    return Agent(
        role="Editor & Fact-Checker",
        goal="Review the draft for factual accuracy, tone, structure, and citation completeness. Fix issues and return the final polished version.",
        backstory=(
            "You are a seasoned editor from The Economist with a zero-tolerance policy for unsupported claims. "
            "You improve writing without changing the author's voice. You always verify citations exist in the research."
        ),
        tools=[],
        llm=settings.LLM_MODEL,
        verbose=True,
        max_iter=3,
    )

def edit_task(agent: Agent, topic: str) -> Task:
    return Task(
        description=f"""
Review and finalise the draft content about: **{topic}**

Check for:
1. **Factual accuracy** — every statistic or claim must appear in the research summary.
   Flag and remove any that cannot be verified.
2. **Citation completeness** — all source URLs from the research must be referenced where relevant.
3. **Clarity and flow** — fix any awkward phrasing, passive voice, or redundant sentences.
4. **Format compliance** — ensure the document matches its intended format (report / linkedin / summary).
5. **Opening strength** — the first sentence must hook the reader. Rewrite if weak.

Return the complete, corrected final document in Markdown. Do not add a preamble — output ONLY the document.
""",
        expected_output="The final polished document in Markdown, with all issues resolved.",
        agent=agent,
    )
```

---

## 6. Tools — Tavily, Firecrawl, RAG

### `backend/tools/search.py`
```python
from crewai.tools import BaseTool
from tavily import TavilyClient
from config import settings
from pydantic import Field

class TavilySearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Search the web for current information. Input: a search query string. "
        "Returns a list of relevant results with titles, URLs, and content snippets."
    )
    client: TavilyClient = Field(default_factory=lambda: TavilyClient(api_key=settings.TAVILY_API_KEY))

    def _run(self, query: str) -> str:
        results = self.client.search(
            query=query,
            search_depth="advanced",
            max_results=8,
            include_answer=True,
        )
        output = []
        if results.get("answer"):
            output.append(f"**Summary:** {results['answer']}\n")
        for r in results.get("results", []):
            output.append(f"- [{r['title']}]({r['url']})\n  {r.get('content', '')[:300]}")
        return "\n".join(output)

tavily_search_tool = TavilySearchTool()
```

### `backend/tools/scraper.py`
```python
from crewai.tools import BaseTool
from firecrawl import FirecrawlApp
from config import settings
from pydantic import Field

class FirecrawlTool(BaseTool):
    name: str = "scrape_webpage"
    description: str = (
        "Scrape the full content of a webpage and return it as clean markdown. "
        "Input: a URL string. Use this to get the full text of articles or reports found via web_search."
    )
    app: FirecrawlApp = Field(default_factory=lambda: FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY))

    def _run(self, url: str) -> str:
        try:
            result = self.app.scrape_url(
                url,
                params={"formats": ["markdown"], "onlyMainContent": True}
            )
            content = result.get("markdown", "")
            # Limit to 6000 chars to avoid context overflow
            return content[:6000] if content else "No content extracted."
        except Exception as e:
            return f"Failed to scrape {url}: {str(e)}"

firecrawl_tool = FirecrawlTool()
```

### `backend/tools/rag.py`
```python
from crewai.tools import BaseTool
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from typing import ClassVar
import uuid

# Module-level in-memory Chroma client — lives for the duration of the process
_client = chromadb.Client()  # ephemeral, in-memory
_embedding_fn = DefaultEmbeddingFunction()

class RAGTool(BaseTool):
    name: str = "search_documents"
    description: str = (
        "Search through uploaded documents for relevant information. "
        "Input: a query string. Returns matching excerpts from the user's uploaded files."
    )
    collection_name: str = "session_docs"

    def _run(self, query: str) -> str:
        try:
            collection = _client.get_collection(
                self.collection_name,
                embedding_function=_embedding_fn
            )
            results = collection.query(query_texts=[query], n_results=4)
            docs = results.get("documents", [[]])[0]
            if not docs:
                return "No relevant documents found."
            return "\n\n---\n\n".join(docs)
        except Exception:
            return "No documents have been uploaded for this session."

def ingest_documents(texts: list[str], collection_name: str = "session_docs"):
    """
    Ingest a list of text chunks into the in-memory Chroma collection.
    Call this after PDF parsing, before running the crew.
    """
    try:
        _client.delete_collection(collection_name)
    except Exception:
        pass
    collection = _client.create_collection(
        collection_name,
        embedding_function=_embedding_fn
    )
    ids = [str(uuid.uuid4()) for _ in texts]
    collection.add(documents=texts, ids=ids)

rag_tool = RAGTool()
```

---

## 7. HITL — Human-in-the-Loop

### Architecture
1. The run service executes the Researcher task first and saves `research_output` to the DB.
2. Status is set to `awaiting_hitl`. The SSE stream emits a `hitl_required` event.
3. The frontend renders a modal with the research summary and an optional instruction field.
4. User clicks Approve (+ optional redirect instruction). Frontend POSTs to `/runs/{id}/approve`.
5. A `asyncio.Event` is set, unblocking the waiting run service coroutine.
6. The crew resumes with the remaining tasks (Analyst, Writer, Editor).

### `backend/services/run_service.py`
```python
import asyncio
from uuid import UUID
from database import AsyncSessionLocal
from models import Run, RunStatus
from agents.researcher import researcher_agent, research_task
from crewai import Crew, Process
from tools.rag import ingest_documents
from datetime import datetime, timezone

# Global event store for HITL — keyed by run_id string
_hitl_events: dict[str, asyncio.Event] = {}
_hitl_instructions: dict[str, str | None] = {}

# SSE event store — keyed by run_id string
_sse_queues: dict[str, asyncio.Queue] = {}

def get_or_create_queue(run_id: str) -> asyncio.Queue:
    if run_id not in _sse_queues:
        _sse_queues[run_id] = asyncio.Queue()
    return _sse_queues[run_id]

async def emit(run_id: str, event_type: str, data: dict):
    """Push an SSE event into the queue for this run."""
    q = get_or_create_queue(run_id)
    await q.put({"type": event_type, "data": data})

async def execute_run(run_id: UUID):
    rid = str(run_id)
    _hitl_events[rid] = asyncio.Event()

    try:
        async with AsyncSessionLocal() as db:
            # Load run
            run = await db.get(Run, run_id)
            if not run:
                return

            # Ingest uploaded documents if any
            context_docs = ""
            if run.doc_paths:
                from services.pdf_service import parse_pdfs
                chunks = await parse_pdfs(run.doc_paths)
                if chunks:
                    ingest_documents(chunks)
                    context_docs = "Documents ingested. Use the search_documents tool to query them."

        # ── PHASE 1: Research only ──
            await _set_status(run, RunStatus.researching, db)
            await emit(rid, "status", {"status": "researching"})

            researcher = researcher_agent()
            r_task = research_task(researcher, run.topic, context_docs)
            research_crew = Crew(
                agents=[researcher],
                tasks=[r_task],
                process=Process.sequential,
                verbose=True,
                step_callback=lambda step: asyncio.create_task(
                    emit(rid, "log", {"agent": "Researcher", "message": str(step)})
                ),
            )
            research_result = await asyncio.to_thread(research_crew.kickoff)
            research_md = str(research_result)

        # Save research output, pause for HITL
            run.research_output = research_md
            await _set_status(run, RunStatus.awaiting_hitl, db)
            await emit(rid, "hitl_required", {
                "research_summary": research_md[:2000]  # send first 2000 chars to frontend
            })

        # Wait for human approval (or timeout after 30 min)
            try:
                await asyncio.wait_for(_hitl_events[rid].wait(), timeout=1800)
            except asyncio.TimeoutError:
                await _set_status(run, RunStatus.failed, db)
                await emit(rid, "error", {"message": "HITL timed out after 30 minutes."})
                return

            extra_instruction = _hitl_instructions.get(rid, "")

        # ── PHASE 2: Analyse, Write, Edit ──
            await _set_status(run, RunStatus.writing, db)
            await emit(rid, "status", {"status": "writing"})

            from agents.analyst import analyst_agent, analysis_task
            from agents.writer import writer_agent, write_task
            from agents.editor import editor_agent, edit_task

            analyst = analyst_agent()
            writer  = writer_agent()
            editor  = editor_agent()

        # Prepend extra instruction if provided
            topic_with_instruction = run.topic
            if extra_instruction:
                topic_with_instruction = f"{run.topic}\n\nAdditional focus: {extra_instruction}"

            a_task = analysis_task(analyst, topic_with_instruction)
            w_task = write_task(writer, topic_with_instruction, run.format)
            e_task = edit_task(editor, topic_with_instruction)

        # Inject research as context
            a_task.context = []  # CrewAI will chain from previous task
            writing_crew = Crew(
                agents=[analyst, writer, editor],
                tasks=[a_task, w_task, e_task],
                process=Process.sequential,
                verbose=True,
                step_callback=lambda step: asyncio.create_task(
                    emit(rid, "log", {
                        "agent": step.agent.role if hasattr(step, 'agent') else "Agent",
                        "message": str(step)
                    })
                ),
            )

        # Provide research output as initial context
            writing_crew.tasks[0].description = (
                f"Research summary:\n{research_md}\n\n" + writing_crew.tasks[0].description
            )

            final_result = await asyncio.to_thread(writing_crew.kickoff)
            run.final_output = str(final_result)
            await _set_status(run, RunStatus.complete, db)
            await emit(rid, "complete", {"output": run.final_output[:500]})

    except Exception as e:
        async with AsyncSessionLocal() as db:
            run = await db.get(Run, run_id)
            if run:
                await _set_status(run, RunStatus.failed, db)
        await emit(rid, "error", {"message": str(e)})
        raise
    finally:
        _hitl_events.pop(rid, None)
        _hitl_instructions.pop(rid, None)

async def approve_hitl(run_id: str, instruction: str | None = None):
    _hitl_instructions[run_id] = instruction
    if run_id in _hitl_events:
        _hitl_events[run_id].set()

async def _set_status(run: Run, status: RunStatus, db: AsyncSession):
    run.status = status
    run.updated_at = datetime.now(timezone.utc)
    db.add(run)
    await db.commit()
```

### `backend/routers/hitl.py`
```python
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from models import Run, RunStatus
from schemas import HitlApproveRequest
from services.run_service import approve_hitl

router = APIRouter()

@router.post("/{run_id}/approve")
async def approve(run_id: UUID, body: HitlApproveRequest, db: AsyncSession = Depends(get_db)):
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.status != RunStatus.awaiting_hitl:
        raise HTTPException(400, f"Run is not awaiting HITL (status: {run.status})")
    await approve_hitl(str(run_id), body.instruction)
    return {"status": "resumed"}
```

---

## 8. Output Formatters

### `backend/formatters/report.py`
```python
def format_report(raw_markdown: str) -> str:
    """
    The Editor's output IS the report — already in markdown.
    This formatter adds a standardised header block if missing.
    """
    if not raw_markdown.startswith("#"):
        raw_markdown = f"# Research Report\n\n{raw_markdown}"
    return raw_markdown
```

### `backend/formatters/linkedin.py`
```python
def format_linkedin(raw_markdown: str) -> str:
    """
    LinkedIn posts do not render markdown. Convert to plain text with spacing.
    Preserve bold via ** only (LinkedIn renders this). Strip other markdown.
    """
    import re
    text = raw_markdown
    # Convert H1/H2/H3 to bold
    text = re.sub(r'^#{1,3} (.+)$', r'**\1**', text, flags=re.MULTILINE)
    # Remove remaining markdown symbols except **
    text = re.sub(r'^#{4,6} ', '', text, flags=re.MULTILINE)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # remove hyperlinks
    text = re.sub(r'`([^`]+)`', r'\1', text)                # inline code
    text = re.sub(r'^\s*[-*] ', '• ', text, flags=re.MULTILINE)  # bullets
    return text.strip()
```

### `backend/formatters/summary.py`
```python
def format_summary(raw_markdown: str) -> str:
    return raw_markdown  # already formatted by the Writer/Editor
```

### `backend/services/pdf_service.py`
```python
import asyncio
from pathlib import Path
import markdown
import weasyprint

async def markdown_to_pdf(md_content: str, output_path: str) -> str:
    """Convert markdown string to PDF file. Returns the output path."""
    html = markdown.markdown(md_content, extensions=["tables", "fenced_code"])
    styled_html = f"""
    <html><head><style>
      body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto;
              line-height: 1.6; color: #333; }}
      h1 {{ color: #1a1a2e; border-bottom: 2px solid #534AB7; padding-bottom: 8px; }}
      h2 {{ color: #333; border-bottom: 1px solid #ddd; padding-bottom: 4px; }}
      table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
      th {{ background: #534AB7; color: white; padding: 8px 12px; }}
      td {{ border: 1px solid #ddd; padding: 8px 12px; }}
      blockquote {{ border-left: 4px solid #534AB7; margin: 0; padding-left: 16px; color: #555; }}
      code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
    </style></head><body>{html}</body></html>
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: weasyprint.HTML(string=styled_html).write_pdf(output_path))
    return output_path

async def parse_pdfs(paths: list[str]) -> list[str]:
    """Parse uploaded PDFs into text chunks using LlamaParse."""
    try:
        from llama_parse import LlamaParse
        from config import settings
        parser = LlamaParse(api_key=settings.LLAMA_CLOUD_API_KEY, result_type="markdown")
        chunks = []
        for path in paths:
            docs = await parser.aload_data(path)
            for doc in docs:
                # Chunk into ~500 word segments
                words = doc.text.split()
                for i in range(0, len(words), 500):
                    chunks.append(" ".join(words[i:i+500]))
        return chunks
    except Exception as e:
        print(f"PDF parse error: {e}")
        return []
```

---

## 9. Database — PostgreSQL

### Schema Migration (run once)
```sql
-- Run via psql or include in alembic migration

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TYPE run_status AS ENUM (
  'pending', 'researching', 'awaiting_hitl', 'writing', 'complete', 'failed'
);

CREATE TABLE IF NOT EXISTS runs (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id         VARCHAR(255) NOT NULL,
  topic           TEXT NOT NULL,
  format          VARCHAR(50) NOT NULL,
  status          run_status NOT NULL DEFAULT 'pending',
  doc_paths       JSONB DEFAULT '[]',
  research_output TEXT,
  final_output    TEXT,
  logs            JSONB DEFAULT '[]',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_runs_user_id ON runs(user_id);
CREATE INDEX idx_runs_status ON runs(status);
CREATE INDEX idx_runs_created_at ON runs(created_at DESC);
```

---

## 10. Frontend — Next.js 15

### `frontend/package.json` (key dependencies)
```json
{
  "dependencies": {
    "next": "15.3.0",
    "react": "19.0.0",
    "react-dom": "19.0.0",
    "next-auth": "^4.24.11",
    "tailwindcss": "^3.4.17",
    "@radix-ui/react-dialog": "^1.1.4",
    "@radix-ui/react-tabs": "^1.1.2",
    "@radix-ui/react-select": "^2.1.4",
    "lucide-react": "^0.383.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.6.0",
    "eventsource-parser": "^3.0.0",
    "react-dropzone": "^14.3.5",
    "react-markdown": "^9.0.1",
    "remark-gfm": "^4.0.0"
  }
}
```

### `frontend/lib/types.ts`
```typescript
export type RunStatus =
  | "pending"
  | "researching"
  | "awaiting_hitl"
  | "writing"
  | "complete"
  | "failed";

export type OutputFormat = "report" | "linkedin" | "summary";

export interface Run {
  id: string;
  topic: string;
  format: OutputFormat;
  status: RunStatus;
  created_at: string;
}

export interface RunDetail extends Run {
  logs: LogEntry[];
  research_output: string | null;
  final_output: string | null;
}

export interface LogEntry {
  agent: string;
  message: string;
  ts: string;
}

export type SSEEvent =
  | { type: "status";       data: { status: RunStatus } }
  | { type: "log";          data: LogEntry }
  | { type: "hitl_required"; data: { research_summary: string } }
  | { type: "complete";     data: { output: string } }
  | { type: "error";        data: { message: string } };
```

### `frontend/lib/api.ts`
```typescript
const BASE = process.env.NEXT_PUBLIC_BACKEND_URL;

async function authHeaders(): Promise<Record<string, string>> {
  // Get a backend-scoped JWT from a frontend API route that validates the NextAuth session.
  const tokenRes = await fetch("/api/backend-token", { method: "GET" });
  if (!tokenRes.ok) throw new Error("Failed to obtain backend auth token.");
  const { token } = await tokenRes.json();
  if (!token) throw new Error("Missing backend auth token.");
  return { Authorization: `Bearer ${token}` };
}

export async function createRun(payload: {
  topic: string;
  format: string;
  doc_ids: string[];
}): Promise<{ id: string }> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getRuns(): Promise<import("./types").Run[]> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/runs`, { credentials: "include", headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getRun(id: string): Promise<import("./types").RunDetail> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/runs/${id}`, { credentials: "include", headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function approveHitl(id: string, instruction?: string) {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/runs/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    credentials: "include",
    body: JSON.stringify({ instruction: instruction ?? null }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function uploadFile(file: File): Promise<{ doc_id: string }> {
  const headers = await authHeaders();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/upload`, {
    method: "POST",
    credentials: "include",
    headers,
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function getOutputUrl(runId: string, format: "pdf" | "md"): string {
  return `${BASE}/runs/${runId}/output/${format}`;
}
```

### `frontend/app/api/backend-token/route.ts`
```typescript
import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import jwt from "jsonwebtoken";

export async function GET() {
  const session = await getServerSession(authOptions);
  const userId = session?.user?.email;
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const secret = process.env.BACKEND_JWT_SECRET;
  if (!secret) {
    return NextResponse.json({ error: "Server misconfigured" }, { status: 500 });
  }

  const token = jwt.sign({ sub: userId }, secret, { algorithm: "HS256", expiresIn: "15m" });
  return NextResponse.json({ token });
}
```

### `frontend/components/AgentLog.tsx`
```tsx
"use client";

import { useEffect, useRef } from "react";
import type { LogEntry } from "@/lib/types";

const AGENT_COLORS: Record<string, string> = {
  "Senior Research Analyst": "text-blue-400",
  "Strategic Insights Analyst": "text-amber-400",
  "Senior Content Writer": "text-green-400",
  "Editor & Fact-Checker": "text-purple-400",
};

export function AgentLog({ logs }: { logs: LogEntry[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="bg-zinc-950 rounded-lg border border-zinc-800 p-4 h-96 overflow-y-auto font-mono text-sm">
      {logs.length === 0 && (
        <p className="text-zinc-500 italic">Waiting for agents to start...</p>
      )}
      {logs.map((log, i) => (
        <div key={i} className="mb-2">
          <span className={`font-bold ${AGENT_COLORS[log.agent] ?? "text-zinc-300"}`}>
            [{log.agent}]
          </span>{" "}
          <span className="text-zinc-300 whitespace-pre-wrap break-words">
            {log.message.slice(0, 400)}
            {log.message.length > 400 && "..."}
          </span>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
```

### `frontend/components/HitlModal.tsx`
```tsx
"use client";

import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { approveHitl } from "@/lib/api";

interface Props {
  runId: string;
  researchSummary: string;
  onApproved: () => void;
}

export function HitlModal({ runId, researchSummary, onApproved }: Props) {
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleApprove() {
    setLoading(true);
    try {
      await approveHitl(runId, instruction || undefined);
      onApproved();
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog.Root open>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-2xl bg-white dark:bg-zinc-900 rounded-xl shadow-2xl p-6">
          <Dialog.Title className="text-xl font-bold mb-2">
            ⏸ Research Complete — Review Before Writing
          </Dialog.Title>
          <Dialog.Description className="text-zinc-500 text-sm mb-4">
            The research agent has finished. Review the summary below, optionally redirect the focus, then approve to continue.
          </Dialog.Description>

          <div className="bg-zinc-50 dark:bg-zinc-800 rounded-lg p-4 max-h-64 overflow-y-auto text-sm mb-4 prose dark:prose-invert prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {researchSummary}
            </ReactMarkdown>
          </div>

          <label className="block text-sm font-medium mb-1">
            Optional: redirect the focus for the writing phase
          </label>
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="e.g. Focus more on pricing strategy and enterprise segment"
            className="w-full border rounded-lg p-3 text-sm resize-none h-20 mb-4 dark:bg-zinc-800 dark:border-zinc-700"
          />

          <div className="flex justify-end gap-3">
            <button
              onClick={handleApprove}
              disabled={loading}
              className="bg-violet-600 hover:bg-violet-700 text-white font-medium px-6 py-2 rounded-lg disabled:opacity-50"
            >
              {loading ? "Resuming…" : "Approve & Continue Writing"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
```

### `frontend/app/runs/[id]/page.tsx`
```tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { createParser } from "eventsource-parser";
import { getRun, getOutputUrl } from "@/lib/api";
import { AgentLog } from "@/components/AgentLog";
import { HitlModal } from "@/components/HitlModal";
import { OutputPanel } from "@/components/OutputPanel";
import type { RunDetail, LogEntry, SSEEvent } from "@/lib/types";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL;

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [hitlSummary, setHitlSummary] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("loading");

  // Load initial run state
  useEffect(() => {
    getRun(id).then((r) => {
      setRun(r);
      setLogs(r.logs ?? []);
      setStatus(r.status);
      if (r.status === "awaiting_hitl" && r.research_output) {
        setHitlSummary(r.research_output.slice(0, 2000));
      }
    });
  }, [id]);

  // Connect to SSE stream
  useEffect(() => {
    if (!id) return;
    const es = new EventSource(`${BACKEND}/runs/${id}/stream`, { withCredentials: true });

    const parser = createParser((event) => {
      if (event.type !== "event") return;
      try {
        const parsed: SSEEvent = JSON.parse(event.data);
        if (parsed.type === "log") {
          setLogs((prev) => [...prev, parsed.data]);
        } else if (parsed.type === "status") {
          setStatus(parsed.data.status);
        } else if (parsed.type === "hitl_required") {
          setHitlSummary(parsed.data.research_summary);
          setStatus("awaiting_hitl");
        } else if (parsed.type === "complete") {
          setStatus("complete");
          getRun(id).then(setRun);
        } else if (parsed.type === "error") {
          setStatus("failed");
        }
      } catch {}
    });

    es.onmessage = (e) => parser.feed(`data: ${e.data}\n\n`);
    es.onerror = () => es.close();

    return () => es.close();
  }, [id]);

  if (!run) return <div className="p-8 text-zinc-500">Loading run...</div>;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{run.topic}</h1>
        <p className="text-zinc-500 text-sm mt-1">
          Format: {run.format} · Status:{" "}
          <span className="capitalize font-medium">{status.replace("_", " ")}</span>
        </p>
      </div>

      <AgentLog logs={logs} />

      {status === "awaiting_hitl" && hitlSummary && (
        <HitlModal
          runId={id}
          researchSummary={hitlSummary}
          onApproved={() => {
            setHitlSummary(null);
            setStatus("writing");
          }}
        />
      )}

      {status === "complete" && run.final_output && (
        <OutputPanel
          content={run.final_output}
          pdfUrl={getOutputUrl(id, "pdf")}
          mdUrl={getOutputUrl(id, "md")}
        />
      )}
    </div>
  );
}
```

### `frontend/components/OutputPanel.tsx`
```tsx
"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  content: string;
  pdfUrl: string;
  mdUrl: string;
}

export function OutputPanel({ content, pdfUrl, mdUrl }: Props) {
  return (
    <div className="border rounded-xl overflow-hidden dark:border-zinc-700">
      <div className="flex items-center justify-between px-4 py-3 bg-zinc-50 dark:bg-zinc-800 border-b dark:border-zinc-700">
        <h2 className="font-semibold">Output</h2>
        <div className="flex gap-2">
          <a href={pdfUrl} target="_blank"
            className="text-sm bg-violet-600 hover:bg-violet-700 text-white px-3 py-1.5 rounded-lg">
            Download PDF
          </a>
          <a href={mdUrl} target="_blank"
            className="text-sm border dark:border-zinc-600 px-3 py-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-700">
            Download MD
          </a>
        </div>
      </div>
      <div className="p-6 prose dark:prose-invert max-w-none overflow-y-auto max-h-[60vh]">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    </div>
  );
}
```

---

## 11. Authentication — NextAuth

### `frontend/lib/auth.ts`
```typescript
import type { NextAuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
  ],
  callbacks: {
    async session({ session }) {
      if (session.user?.email) {
        (session.user as any).id = session.user.email;
      }
      return session;
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
};
```

### `frontend/app/api/auth/[...nextauth]/route.ts`
```typescript
import NextAuth from "next-auth";
import { authOptions } from "@/lib/auth";

const handler = NextAuth(authOptions);
export { handler as GET, handler as POST };
```

### Backend — Extracting user_id from NextAuth session
```python
# backend/auth.py — simplified auth dependency
# Frontend sends a backend-scoped bearer token:
# Authorization: Bearer <backend_token>
# Backend verifies this token with SECRET_KEY and extracts "sub" as user_id.

from fastapi import HTTPException, Header
import jwt as pyjwt
from config import settings

def get_current_user(authorization: str = Header(...)) -> str:
    """Extract user_id from backend bearer token."""
    try:
        token = authorization.replace("Bearer ", "")
        payload = pyjwt.decode(token, settings.BACKEND_JWT_SECRET, algorithms=["HS256"])
        return payload.get("sub") or payload.get("email")
    except Exception:
        raise HTTPException(401, "Invalid or missing auth token")
```

---

## 12. Streaming — SSE

### `backend/routers/stream.py`
```python
from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse
from uuid import UUID
import asyncio, json
from services.run_service import get_or_create_queue

router = APIRouter()

@router.get("/{run_id}/stream")
async def stream_run(run_id: UUID):
    rid = str(run_id)
    queue = get_or_create_queue(rid)

    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30)
                yield {"data": json.dumps(event)}
                if event.get("type") in ("complete", "error"):
                    break
            except asyncio.TimeoutError:
                yield {"data": json.dumps({"type": "ping"})}

    return EventSourceResponse(event_generator())
```

### `backend/routers/runs.py`
```python
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from schemas import CreateRunRequest, RunResponse, RunDetailResponse
from models import Run
from sqlalchemy import select
from services.run_service import execute_run
from routers.upload import UPLOAD_DIR
from auth import get_current_user
from pathlib import Path

router = APIRouter()

@router.post("", response_model=RunResponse, status_code=201)
async def create_run(
    body: CreateRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    doc_paths = [str(Path(UPLOAD_DIR) / f"{doc_id}.pdf") for doc_id in body.doc_ids]

    run = Run(
        user_id=user_id,
        topic=body.topic,
        format=body.format,
        doc_paths=doc_paths,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    background_tasks.add_task(execute_run, run.id)
    return run

@router.get("", response_model=list[RunResponse])
async def list_runs(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    result = await db.execute(
        select(Run).where(Run.user_id == user_id).order_by(Run.created_at.desc()).limit(10)
    )
    return result.scalars().all()

@router.get("/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    from uuid import UUID
    run = await db.get(Run, UUID(run_id))
    if not run:
        from fastapi import HTTPException
        raise HTTPException(404, "Run not found")
    if run.user_id != user_id:
        from fastapi import HTTPException
        raise HTTPException(404, "Run not found")
    return run
```

### `backend/routers/outputs.py`
```python
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from database import get_db
from models import Run, RunStatus
from services.pdf_service import markdown_to_pdf
from starlette.background import BackgroundTask
import tempfile, os

router = APIRouter()

@router.get("/{run_id}/output/pdf")
async def download_pdf(run_id: UUID, db: AsyncSession = Depends(get_db)):
    run = await db.get(Run, run_id)
    if not run or run.status != RunStatus.complete:
        raise HTTPException(404, "Output not available")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = f.name
    await markdown_to_pdf(run.final_output, path)
    return FileResponse(
        path,
        filename=f"report_{run_id}.pdf",
        media_type="application/pdf",
        background=BackgroundTask(lambda p: os.remove(p), path),
    )

@router.get("/{run_id}/output/md")
async def download_md(run_id: UUID, db: AsyncSession = Depends(get_db)):
    run = await db.get(Run, run_id)
    if not run or run.status != RunStatus.complete:
        raise HTTPException(404, "Output not available")
    return PlainTextResponse(run.final_output,
                             headers={"Content-Disposition": f'attachment; filename="report_{run_id}.md"'})
```

### `backend/routers/upload.py`
```python
from fastapi import APIRouter, UploadFile, File, HTTPException
import os, uuid, shutil

router = APIRouter()
UPLOAD_DIR = "/tmp/research_factory_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_TYPES = {"application/pdf"}
MAX_SIZE_MB = 20

@router.post("")
async def upload_file(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "Only PDF files are accepted")
    content = await file.read()
    if len(content) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"File exceeds {MAX_SIZE_MB}MB limit")
    doc_id = str(uuid.uuid4())
    path = os.path.join(UPLOAD_DIR, f"{doc_id}.pdf")
    with open(path, "wb") as f:
        f.write(content)
    return {"doc_id": doc_id, "path": path, "filename": file.filename}
```

---

## 13. API Routes Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/runs` | Create a new run and start execution |
| `GET` | `/runs` | List last 10 runs for the current user |
| `GET` | `/runs/{id}` | Get run detail including logs and output |
| `GET` | `/runs/{id}/stream` | SSE stream of agent events |
| `POST` | `/runs/{id}/approve` | HITL approval with optional instruction |
| `GET` | `/runs/{id}/output/pdf` | Download final output as PDF |
| `GET` | `/runs/{id}/output/md` | Download final output as Markdown |
| `POST` | `/upload` | Upload PDF document, returns doc_id |

---

## 14. V2 Extensions

> **Do not build these for V1.** Implement in the order listed below after V1 is shipped and a paying client confirmed.

### 14.1 Persistent Vector DB (Week 3)

Replace `tools/rag.py` in-memory Chroma with Supabase + pgvector:

```python
# Replace chromadb with:
# pip install supabase vecs sentence-transformers

import vecs
from sentence_transformers import SentenceTransformer

# Connection: vecs.create_client(settings.SUPABASE_DB_URL)
# Collection persists across sessions per user_id
# Hybrid search: pgvector cosine similarity + tsvector keyword match
```

New env vars needed:
```env
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
SUPABASE_DB_URL=postgresql://postgres:password@db.xxx.supabase.co:5432/postgres
```

### 14.2 LangGraph Supervisor (Week 3)

Replace the sequential `build_crew` in `crew.py` with a LangGraph StateGraph:

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Literal

class ResearchState(TypedDict):
    topic: str
    task_type: Literal["research_report", "lead_intel", "quick_snapshot"]
    research_output: str
    analysis_output: str
    final_output: str

# Supervisor node inspects task_type and routes to agent subgraphs
# "quick_snapshot" → skip Firecrawl, skip Analyst deep-dive
# "lead_intel" → route to Lead Intelligence subgraph instead of Writer
```

### 14.3 Lead Intelligence Agent (Week 4)

New agent and task. Input: company URL. Output: prospect dossier.

```python
# agents/lead_intel.py
# Tools: Firecrawl (scrape company site), Tavily (search news + funding),
#        LinkedIn scrape via Firecrawl (company page + top employees)
# Output sections:
#   - Company Overview (size, founded, HQ, funding)
#   - Key Decision Makers (name, title, LinkedIn URL)
#   - Recent News (last 3 months)
#   - Technology Stack (from job listings + BuiltWith)
#   - Fit Score (1–10) with reasoning
```

### 14.4 LLM-as-Judge Evaluation (Week 3)

After the Editor task completes, run a separate evaluation call:

```python
# services/eval_service.py

async def evaluate_output(content: str, research: str, topic: str) -> dict:
    """
    Call the configured LLM to score output on 4 dimensions (0-100 each).
    Returns: { accuracy, relevance, completeness, writing_quality, overall, issues }
    """
    prompt = f"""
You are a quality evaluator. Score this content on 4 dimensions (0-100):
1. Accuracy: Are all claims supported by the research?
2. Relevance: Does it address the topic directly?
3. Completeness: Are all required sections present and substantive?
4. Writing Quality: Is it clear, engaging, and professional?

Topic: {topic}

Research Summary:
{research[:2000]}

Content to Evaluate:
{content[:3000]}

Respond ONLY with valid JSON:
{{"accuracy": 85, "relevance": 90, "completeness": 78, "writing_quality": 88, "overall": 85, "issues": ["list any critical issues"]}}
"""
    # Call via LiteLLM for provider-agnostic routing
    from litellm import acompletion
    from config import settings

    response = await acompletion(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL or None,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
    )
    import json
    return json.loads(response.choices[0].message.content)
```

### 14.5 Publisher Agent (Week 4)

```python
# agents/publisher.py
# Triggers after HITL approval IF user set a schedule time
# LinkedIn API: POST to /ugcPosts with scheduled publish time
# Buffer API: POST to /updates/create with profile_ids and scheduled_at
# Env vars needed:
#   LINKEDIN_ACCESS_TOKEN=
#   BUFFER_ACCESS_TOKEN=
```

### 14.6 React Flow Agent Graph (Week 4)

Add to `frontend/components/AgentGraph.tsx`:

```tsx
// npm install @xyflow/react
import { ReactFlow, Node, Edge } from "@xyflow/react";

// Nodes: Input → Researcher → [HITL] → Analyst → Writer → Editor → Output
// Node states: "idle" | "running" | "complete" | "error"
// Running node pulses with a CSS animation
// Completed node shows green border + tick
// Click any completed node to view its output in a side panel
```

### 14.7 Multi-User Workspaces (Week 5)

New DB tables:
```sql
CREATE TABLE workspaces (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name VARCHAR(255) NOT NULL,
  owner_id VARCHAR(255) NOT NULL,
  settings JSONB DEFAULT '{}'
);

CREATE TABLE workspace_members (
  workspace_id UUID REFERENCES workspaces(id),
  user_id VARCHAR(255) NOT NULL,
  role VARCHAR(50) NOT NULL DEFAULT 'viewer', -- viewer | operator | admin
  PRIMARY KEY (workspace_id, user_id)
);

ALTER TABLE runs ADD COLUMN workspace_id UUID REFERENCES workspaces(id);
```

### 14.8 Docker Compose (Week 6)

```yaml
# docker-compose.yml
version: "3.9"
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: research_factory
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    volumes:
      - pgdata:/var/lib/postgresql/data

  backend:
    build: ./backend
    env_file: ./backend/.env
    depends_on: [db]
    ports: ["8000:8000"]
    command: uvicorn main:app --host 0.0.0.0 --port 8000

  frontend:
    build: ./frontend
    env_file: ./frontend/.env.local
    ports: ["3000:3000"]
    depends_on: [backend]

volumes:
  pgdata:
```

---

## 15. Deployment

### V1 — Vercel + Railway

**Frontend (Vercel):**
```bash
cd frontend
npx vercel --prod
# Set env vars in Vercel dashboard:
# NEXTAUTH_URL, NEXTAUTH_SECRET, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
# NEXT_PUBLIC_BACKEND_URL
```

**Backend (Railway):**
```bash
# railway.json
{
  "build": { "builder": "nixpacks" },
  "deploy": {
    "startCommand": "uvicorn main:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "on_failure"
  }
}
# Provision: Railway PostgreSQL plugin → copy DATABASE_URL to env vars
# Set all backend env vars in Railway dashboard
```

### CORS in production
```python
# backend/main.py — update after deploying frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-app.vercel.app",
        settings.FRONTEND_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 16. Testing Checklist

Run through this checklist before recording your Loom demo.

### Backend
- [ ] `GET /health` returns `{"status": "ok"}`
- [ ] `POST /runs` creates a run record and returns an ID
- [ ] SSE stream connects and emits `ping` events while idle
- [ ] Researcher agent runs and emits log events
- [ ] `status` transitions: `pending → researching → awaiting_hitl`
- [ ] `hitl_required` SSE event fires with `research_summary`
- [ ] `POST /runs/{id}/approve` unblocks the crew
- [ ] `status` transitions: `awaiting_hitl → writing → complete`
- [ ] `complete` SSE event fires after Editor finishes
- [ ] `GET /runs/{id}/output/pdf` returns a valid PDF
- [ ] `GET /runs/{id}/output/md` returns markdown text
- [ ] `POST /upload` stores a PDF and returns `doc_id`
- [ ] RAG tool returns excerpts when uploaded doc is queried

### Frontend
- [ ] Dashboard loads and shows last 10 runs
- [ ] New run form validates topic (min 3 chars) and format selection
- [ ] PDF upload accepts .pdf, rejects .docx
- [ ] Run detail page connects to SSE stream automatically
- [ ] AgentLog panel auto-scrolls as logs arrive
- [ ] HITL modal appears when `hitl_required` event fires
- [ ] HITL modal shows research summary
- [ ] Approve without instruction works; approve with instruction works
- [ ] Output panel renders after `complete` event
- [ ] PDF download triggers file download
- [ ] MD download triggers file download
- [ ] Dark mode renders correctly throughout
- [ ] Mobile layout is usable on 375px viewport

### End-to-End Demo Flow
- [ ] Topic: "Competitive landscape for Notion in project management, 2025"
- [ ] Format: "report"
- [ ] No PDF upload (clean run)
- [ ] Watch streaming logs for all 4 agent phases
- [ ] HITL pause fires — add instruction: "Focus on enterprise pricing and Atlassian competition"
- [ ] Writing phase completes
- [ ] Download PDF and verify it opens correctly
- [ ] Check session history shows the completed run
- [ ] Re-open the run from history and verify output is still there

---

## Decisions (Spec Freeze)

### Auth Flow
- Frontend validates user session with NextAuth and mints a short-lived backend JWT at `GET /api/backend-token`.
- Backend verifies bearer tokens with `BACKEND_JWT_SECRET` and resolves `user_id` from `sub` (fallback `email`).
- Protected run routes enforce ownership checks so users can only read/approve/download their own runs.

### Model Abstraction
- LLM access stays provider-agnostic through config (`LLM_MODEL` for legacy single-provider mode, or per-agent provider keys/models for routed mode).
- Agent/task orchestration remains unchanged while model/provider is swapped by environment only.

### Run Lifecycle
- Canonical status progression is:
  `pending -> researching -> awaiting_hitl -> writing -> complete|failed`.
- Research phase pauses at HITL checkpoint; approval resumes writing phase.
- Crew execution runs off the event loop via `asyncio.to_thread` to avoid blocking FastAPI async handlers.

## Changelog

### 2026-05-19 (v1 spec locked)
- Added explicit `Decisions` section for auth flow, model abstraction, and run lifecycle.
- Locked P0 API expectations around route protection and ownership behavior.
- Confirmed P0 lifecycle semantics and HITL pause/resume behavior as canonical.
