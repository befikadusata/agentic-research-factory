# Evaluation Set — 20 Fixed Topics

This eval set is used for benchmarking the Agentic Research Factory across all 3 verticals plus general research. Each topic is run in a controlled environment with the same LLM model and configuration.

---

## Topics

### General Research (6 topics)

| # | Topic | Format |
|---|-------|--------|
| 1 | The state of large language model fine-tuning in 2025 — costs, methods, and ROI | report |
| 2 | Kubernetes cost optimization strategies for mid-size SaaS companies | report |
| 3 | How RAG architectures compare to long-context LLMs for enterprise search | report |
| 4 | The impact of AI on junior software engineering hiring in 2025 | linkedin |
| 5 | Edge computing trends and market outlook for IoT applications | summary |
| 6 | Open-source vs proprietary LLMs: total cost of ownership analysis | report |

### B2B Sales Lead Intel (5 topics)

| # | Company URL | Target Role | Our Product |
|---|------------|-------------|-------------|
| 7 | https://stripe.com | VP Engineering | API monitoring platform |
| 8 | https://notion.so | Head of Product | AI writing assistant |
| 9 | https://linear.app | CTO | Developer productivity suite |
| 10 | https://datadog.com | VP Infrastructure | Cost optimization platform |
| 11 | https://vercel.com | Head of Platform | Edge computing framework |

### Marketing Competitor Briefs (5 topics)

| # | Competitor | Our Product | Target Market |
|---|-----------|-------------|---------------|
| 12 | Notion | AI writing assistant for startups | Series A SaaS founders |
| 13 | HubSpot | Lightweight CRM for dev tools | PLG companies under 100 employees |
| 14 | Figma | AI-powered design tool | Solo designers and small agencies |
| 15 | Intercom | AI support chatbot | E-commerce brands |
| 16 | Ahrefs | AI SEO content platform | Content marketing teams |

### Founder Strategy Briefs (4 topics)

| # | Market Segment | Stage | Key Question |
|---|---------------|-------|-------------|
| 17 | AI-powered legal tech for SMBs | Seed | Is now the right time to enter the SMB legal market? |
| 18 | Vertical SaaS for construction project management | Pre-seed | Can a startup compete with Procore in the mid-market? |
| 19 | AI tutoring for K-12 education | Series A | What's the fastest path to $1M ARR? |
| 20 | Developer tools for AI agent orchestration | Pre-idea | Is this a real category or a feature? |

---

## Metrics Captured Per Run

| Metric | Source |
|--------|--------|
| `latency_sec` | Wall clock time from run start to completion |
| `citations` | Count of `[text](url)` links in final output |
| `research_citations` | Count of links in research summary |
| `eval.accuracy` | LLM-as-Judge: factual accuracy (1–10) |
| `eval.relevance` | LLM-as-Judge: topic relevance (1–10) |
| `eval.depth` | LLM-as-Judge: analytical depth (1–10) |
| `eval.clarity` | LLM-as-Judge: writing clarity (1–10) |
| `completion` | Boolean: did the run reach `complete` status? |

---

## Running the Benchmark

```bash
# Run all 20 topics via the API (requires auth token)
python docs/scripts/run_eval_set.py --env production --output docs/eval_results.md
```

Or manually: create each run via the UI, wait for completion, then aggregate metrics from `GET /analytics/metrics`.
