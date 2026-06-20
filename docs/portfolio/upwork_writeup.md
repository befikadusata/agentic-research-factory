# Upwork Portfolio Writeup

## Agentic Research Factory

**AI-powered research automation with human-in-the-loop quality control**

### What I Built

A production-grade platform that turns a topic into a polished, cited research report using a multi-agent AI pipeline with real-time streaming and human checkpoints.

**3 specialised verticals**: 🎯 B2B Sales Lead Intel · 📊 Marketing Competitor Briefs · 🚀 Founder Strategy Briefs

### Architecture

- **Backend**: FastAPI + LangGraph + CrewAI (5 agents) + Tavily + Firecrawl + RAG
- **Frontend**: Next.js 15 + SSE streaming + HITL modal + PDF/MD export
- **Infra**: PostgreSQL (pgvector), async Python, structured logging, retry/fallback

### Key Results

| Metric | Value |
|--------|-------|
| Avg. report time | ~8 min |
| Avg. citations | 12+ per report |
| Cost per report | ~$0.35 |

### Tech Stack

`Python` · `FastAPI` · `LangGraph` · `CrewAI` · `Next.js 15` · `React 19` · `PostgreSQL` · `Tavily` · `Firecrawl` · `LiteLLM` · `SSE` · `Tailwind CSS`
