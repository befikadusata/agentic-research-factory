# Reliability Guide

## Overview

Known failure modes of the Agentic Research Factory, what the system does about
each, and what reaches the user.

---

## External Dependencies

| Service | Purpose | Failure Impact |
|---------|---------|----------------|
| **Tavily** | Web search, 8 results per query | Research phase has fewer sources |
| **SearXNG** | Web search alternative; takes priority over Tavily whenever `SEARXNG_URL` is set. Returns 4 results, snippets trimmed to 150 chars | Same |
| **Firecrawl** | Full-page scraping | Analysis relies on search snippets only |
| **LLM providers** (litellm → Groq / OpenRouter, see `services/llm_router.py`) | Agent reasoning, writing, evaluation | Stage fails after retries and cross-provider fallback are exhausted; the run fails |
| **PostgreSQL** | Run persistence, metrics, pgvector store | `/health` returns 503 and every request touching a run fails. The process still boots — the lifespan hook validates config and opens the Redis pool, not the DB |
| **Redis** | Celery broker/backend, SSE pub/sub, embedding cache | `/health` returns 503; no runs can be dispatched or streamed |
| **SMTP / webhook endpoint** | Monitor change alerts | Alert is dropped (logged); the run itself is unaffected |

---

## Failure Modes & Behaviour

### Where degradation messages go

Tool-level fallbacks are **return values handed back to the agent**, not SSE
events. The agent reads the `⚠️ …` string as tool output and keeps reasoning
with reduced data; the user sees the consequence in the final report, not a
notice in the log stream. Only `emit()` calls produce SSE events, and no tool
calls it.

### Web search failures

Both the Tavily and SearXNG tools wrap their network call in
`@retry(stop_after_attempt(3), wait_exponential(multiplier=1, min=2, max=10))`
and catch everything the retries do not fix.

| Scenario | System Behaviour | Result |
|----------|-----------------|--------|
| **Rate limited (429)** | 3 attempts with backoff (~2s, ~4s) | On exhaustion the tool returns `⚠️ Web search temporarily unavailable (Tavily: <ExcType>)…` to the agent; the run continues |
| **API key invalid** | Also 3 attempts — the retry predicate does not discriminate by error type, so an auth error costs the full backoff before failing | Same fallback string; output will lack external sources |
| **Network timeout** | 3 attempts with backoff (SearXNG additionally caps the HTTP call at 30s) | Same fallback; run continues |

### Firecrawl scraping failures

| Scenario | System Behaviour | Result |
|----------|-----------------|--------|
| **Not configured** | Short-circuits *before* the retry decorator — with no key every attempt fails identically, so retrying only adds ~6s of backoff per URL | `⚠️ Page scraping unavailable for {url} (Firecrawl: not configured)` |
| **Page blocked / rate limited (single-URL `scrape_webpage`)** | 3 attempts with backoff | Same message with the exception type as the reason |
| **Batch path (`batch_scrape_webpages`)** | **No retries.** Each URL gets one attempt under a 60s `asyncio.wait_for` | That URL's entry becomes `Error: <msg>`; the other URLs are unaffected |

### LLM / agent failures

There is **no error classification layer.** `execute_run` catches at the top of
the segment, persists `str(e)[:500]` to `run.error_message`, sets the run
`failed`, and emits one SSE `error` event carrying `Run failed: <first 200
chars>`. The frontend renders that string verbatim. Rate limits, auth errors and
timeouts are therefore all surfaced as the provider's own raw message.

| Scenario | System Behaviour |
|----------|-----------------|
| **Node failure inside a graph invoke** | `_invoke_supervisor_with_retry` retries up to 3× with exponential backoff, resuming from the LangGraph checkpoint (`input=None`) on attempts 2 and 3 |
| **`StageTimeout`** | **Terminal — never retried.** `retry_if_not_exception_type(StageTimeout)` excludes it, because retrying is what the shared segment budget exists to prevent |
| **Provider 429 / outage** | litellm tries the cross-provider `fallbacks` list first (Groq-primary spills to OpenRouter and vice versa, gated on the peer key being present) before the exception reaches the retry layer |
| **Per-run spend ceiling reached** | At `RUN_COST_CEILING_USD` (default `$1.00`) the reviewer retry loop stops re-running the research→analyse→review triad and the graph ships what it has. Set `None` or `<= 0` to disable; the retry cap of 3 still bounds the loop |

Celery records the task FAILED by re-raising a plain `RuntimeError` rather than
the original exception — tenacity's `RetryError` embeds an unpickleable
`concurrent.futures.Future` that crashes the result backend.

### LLM-as-judge evaluation failures

| Scenario | System Behaviour | Result |
|----------|-----------------|--------|
| **Any eval error** | Caught, logged as `eval_failed` at `WARNING`, returns `{}` | No SSE notice is emitted. `run.metrics.eval` is `{}`; the run completes normally with no eval scores |

### Monitor change-detection failures

| Scenario | System Behaviour | Result |
|----------|-----------------|--------|
| **Diff LLM call fails** | `_diff_runs` returns `{"changed": False, "summary": "Change detection unavailable.", "error": …}` | No alert fires; the run still completes |
| **Webhook POST fails** | Best-effort under a 15s `httpx` timeout; logged as `monitor_alert_webhook_failed` | Alert dropped, run unaffected |
| **`finalize_monitored_run` raises anywhere** | Whole body is wrapped; logged as `monitor_finalize_failed` | A failed diff can never fail the run |

### Document ingestion

| Scenario | System Behaviour | Result |
|----------|-----------------|--------|
| **A referenced document is `failed`** | Run marked `failed` immediately | SSE error: `Document ingestion failed for: {filenames}` |
| **Documents still `pending` after 300s** | Polled every 5s; run marked `failed` on timeout | SSE error: `Timed out waiting for document ingestion` |

### Human-in-the-loop gates

**A manual run parked at an approval gate waits indefinitely.** HITL waits happen
*between* Celery tasks, not inside them: `_enter_gate` persists an `awaiting_*`
status and the worker returns, so a paused run holds no worker and burns no task
time limit. Approval enqueues the next segment in a fresh worker child.

The beat-driven reaper (`reap_orphaned_runs`, every 300s) fails runs whose
`updated_at` is older than `RUN_STUCK_TIMEOUT_MIN` (default 20 min) with
`Run reaped: stuck with no worker progress past the timeout.` — but it
deliberately skips manual runs sitting at an `awaiting_*` gate, since those are
legitimately waiting on a human. It reaps non-terminal runs with no live task
(`pending` / `researching` / `analyzing` / `writing`) and *autonomous*
monitor-spawned runs parked at a gate whose auto-advance dispatch was lost. The
timeout must stay above the Celery hard limit (~11 min) plus a margin so a
still-running segment is never mistaken for a dead one.

---

## Retry Configuration

Tool-level and stage-level retries both use `tenacity`:

```
stop:  after 3 attempts
wait:  exponential(multiplier=1, min=2s, max=10s)
```

- Attempt 1: immediate
- Attempt 2: after ~2s
- Attempt 3: after ~4s
- Total ~6s of backoff before the fallback path

Only `_invoke_supervisor_with_retry` passes `before_sleep=before_sleep_log(logger,
WARNING)`; the tool decorators in `tools/search.py`, `tools/scraper.py` and
`tools/rag.py` do not, so their intermediate attempts are silent and only the
final failure is logged by the surrounding `except`.

## Timeout & Budget Configuration

Sourced from `backend/config.py` unless noted.

| Boundary | Value | Behaviour on expiry |
|----------|-------|---------------------|
| Celery task soft limit (`TASK_SOFT_TIME_LIMIT_SEC`) | 600s | `SoftTimeLimitExceeded`; the task can still clean up |
| Celery task hard limit (`TASK_TIME_LIMIT_SEC`) | 660s | `SIGKILL`. `worker_max_tasks_per_child=1` recycles the child after every task regardless |
| **Segment LLM budget** (`run_service.SEGMENT_BUDGET_SEC`) | **540s** = soft limit − `SEGMENT_BUDGET_MARGIN_SEC` (60s) | One `_Budget` deadline shared by *every* graph invoke in a task, so 3 retries × 2 invokes cannot add up past the soft limit. Exceeding it raises `StageTimeout` and the segment fails *inside* its own task, persisting `failed` + an error message instead of being killed mid-flight |
| Per-invoke cap (`LLM_STAGE_TIMEOUT_SEC`) | 300s, clamped to `min(300, SEGMENT_BUDGET_SEC)` | The segment budget can shrink it further; a misconfigured per-stage value cannot exceed the segment bound |
| Stuck-run reaper (`RUN_STUCK_TIMEOUT_MIN`) | 20 min | Run marked `failed`; see the HITL section for what is exempt |
| Per-run spend ceiling (`RUN_COST_CEILING_USD`) | $1.00 | Reviewer retry loop stops; the graph ships what it has |
| Document ingestion poll | 300s, 5s interval (`run_service`) | Run marked `failed`; error message written and emitted |
| PDF parse, Docling (`pdf_service.PDF_PARSE_TIMEOUT_SEC`) | 120s | Falls through to LlamaParse *if* `LLAMA_CLOUD_API_KEY` is set, otherwise `parse_pdf` returns `[]` and the document is recorded with no extractable text |
| Eval LLM call (`eval_service`) | 60s | Eval skipped; run still completes |
| Monitor diff LLM call | 60s | Fallback diff; no alert |
| Monitor webhook POST | 15s | Alert dropped |
| Batch scrape, per URL | 60s | That URL returns an error string; others unaffected |
| SearXNG HTTP call | 30s | Counts as one failed attempt |
| SSE keep-alive heartbeat (`stream.HEARTBEAT_INTERVAL`) | 30s | `data: heartbeat` sent to hold the connection open |
| SSE max stream duration (`stream.MAX_STREAM_DURATION`) | 3600s | Generator closes; the client reconnects if needed |
| Health check DB/Redis probe | 2s each | `/health` returns 503 with the failing dependency marked `error` |

### Researcher pass budget

The first researcher pass is deliberately shallow — `RESEARCHER_MAX_ITER` 2
ReAct iterations and `RESEARCHER_MAX_TOKENS` 900 — to fit Groq's free
12K-tokens/min ceiling. On a retry (which only happens after the reviewer FAILed
the prior pass) the budget escalates by `RESEARCHER_RETRY_TOKEN_STEP` (500) per
retry, because repeating the same undersized pass just re-fails and re-bills it.
Raise the base values on a paid key.

---

## Monitoring

- Failures are logged via `structlog` with structured fields (`run_id`,
  `query`/`url`, `error`).
- Request IDs (`X-Request-ID`) propagate through all logs; the middleware
  generates one when the header is absent and echoes it on the response.
- Prometheus metrics are exposed at `/metrics`.
- SSE events surface **run-level** status, error and completion to the user in
  real time. Tool-level degradation is not among them (see above).

---

## Design Principles

1. **Never fail silently** — every failure emits a structured log event. Run-level
   failures additionally emit an SSE `error` event; tool-level ones do not.
2. **Degrade, don't block** — tool failures return fallback text to the agent, so
   the agent continues reasoning with reduced data.
3. **Bound the segment, not just the call** — per-invoke timeouts do not compose
   into a task bound, so one shared wall-clock deadline governs the whole
   segment. Failing inside the task beats being SIGKILLed outside it.
4. **Eval and monitoring are optional** — quality scoring, change detection and
   alerting never block output delivery.
