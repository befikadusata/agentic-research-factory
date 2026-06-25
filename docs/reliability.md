# Reliability Guide

## Overview

The Agentic Research Factory is designed to degrade gracefully when external dependencies fail. This document describes known failure modes, what the system does, and what the user sees.

---

## External Dependencies

| Service | Purpose | Failure Impact |
|---------|---------|----------------|
| **Tavily** | Web search (8 results per query) | Research phase has fewer sources |
| **Firecrawl** | Full-page scraping | Analysis relies on search snippets only |
| **LLM (OpenAI/Litellm)** | Agent reasoning, writing, evaluation | Run fails if all retries exhausted |
| **PostgreSQL** | Run persistence, metrics | App cannot start |

---

## Failure Modes & Behaviour

### Tavily Search Failures

| Scenario | System Behaviour | User Sees |
|----------|-----------------|-----------|
| **Rate limited (429)** | 3 retries with exponential backoff (2s→4s→10s) | If all retries fail: SSE log shows "⚠️ Web search temporarily unavailable" — run continues with available data |
| **API key invalid** | Immediate failure, no retry | Same fallback message; output will lack external sources |
| **Network timeout** | 3 retries with backoff | Same fallback; run continues |

### Firecrawl Scraping Failures

| Scenario | System Behaviour | User Sees |
|----------|-----------------|-----------|
| **Page blocked (403/captcha)** | 3 retries, then fallback | SSE log: "⚠️ Page scraping unavailable for {url}" — analysis uses search snippet data |
| **Rate limited** | 3 retries with backoff | Same fallback message |
| **Timeout (slow page)** | Per-URL 60s timeout via `asyncio.wait_for`; returns error string for that URL | Same; output notes reduced source depth |

### LLM / Agent Failures

| Scenario | System Behaviour | User Sees |
|----------|-----------------|-----------|
| **Rate limited (429)** | Run fails with classified error | "Rate limited by the AI provider. Please wait a minute and try again." |
| **Timeout** | Run fails | "The research timed out. Try a more focused topic." |
| **Auth error** | Run fails | "AI service authentication error. Please contact support." |
| **Unknown error** | Run fails | First 200 chars of the error message |

### LLM-as-Judge Evaluation Failures

| Scenario | System Behaviour | User Sees |
|----------|-----------------|-----------|
| **Any eval error** | Eval skipped; run still completes | SSE log: "⚠️ Quality evaluation skipped — output is still complete" |
| **Impact** | `run.metrics.eval` will be `{}` | No eval scores in output; run marked complete normally |

### HITL Timeout

| Scenario | System Behaviour | User Sees |
|----------|-----------------|-----------|
| **No approval in 30 min** | Run marked `failed` | SSE error: "HITL timed out after 30 minutes" |

---

## Retry Configuration

All retries use `tenacity` with exponential backoff. Retry attempts are logged at `WARNING` level via `before_sleep_log`.

```
stop:  after 3 attempts
wait:  exponential(multiplier=1, min=2s, max=10s)
```

This means:
- Attempt 1: immediate
- Attempt 2: after ~2s
- Attempt 3: after ~4s
- Total max wait: ~6s before fallback

## Timeout Configuration

| Boundary | Timeout | Behaviour on expiry |
|----------|---------|---------------------|
| LLM supervisor stage | 300s per stage | Stage fails; `tenacity` retries up to 3× |
| HITL wait | 30 min | Run marked `failed`; SSE error event emitted |
| Document ingestion poll | 300s | Run marked `failed`; error message written |
| PDF parse (Docling) | 120s | Falls through to LlamaParse fallback |
| Eval LLM call | 60s | Eval skipped; run still completes |
| Batch scrape per-URL | 60s | URL returns error string; other URLs unaffected |
| SSE keep-alive heartbeat | 30s between messages | `data: heartbeat` sent to keep connection alive |
| SSE max stream duration | 3600s | Generator closes; client reconnects if needed |
| Celery task soft limit | 600s | `SoftTimeLimitExceeded` raised; task can clean up |
| Celery task hard limit | 660s | `SIGKILL`; worker process restarted |
| Health check DB/Redis probe | 2s each | `/health` returns 503 with failed dependency name |

---

## Monitoring

- All failures are logged via `structlog` with structured fields (`run_id`, `query`/`url`, `error`).
- Request IDs (`X-Request-ID` header) propagate through all logs for traceability.
- SSE events surface degradation notices to the user in real time.

---

## Design Principles

1. **Never crash silently** — every failure emits a structured log event AND an SSE message.
2. **Degrade, don't block** — tool failures return fallback text to the agent; the agent continues reasoning with reduced data.
3. **Classify errors for users** — the top-level exception handler maps raw errors to human-readable messages (rate limit, timeout, auth, generic).
4. **Eval is optional** — quality scoring never blocks output delivery.
