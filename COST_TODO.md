# LLM & API Cost Optimization TODO

## Phase 1: Tiered Model Routing (Configurability)
- [ ] **Config Registry**: Update `backend/config.py` to support `AGENT_MODEL_MAP` (Researcher, Analyst, Writer, Reviewer, Strategist).
- [ ] **Schema Extension**: Update `CreateRunRequest` in `backend/schemas.py` to allow optional `model_overrides: dict`.
- [ ] **Agent Injection**: Refactor agents in `backend/agents/` to use specific models from the registry instead of a global default.
- [ ] **Eval Optimization**: Update `backend/services/eval_service.py` to use a lightweight model for quality scoring.

## Phase 2: Semantic Tool Caching (24h Efficiency)
- [ ] **Redis Infrastructure**: Implement `backend/utils/cache.py` with Redis client and TTL support.
- [ ] **Tool Decorators**: Wrap `tavily_search` and `firecrawl_scrape` with `@tool_cache(ttl=86400)`.
- [ ] **Key Normalization**: Implement query normalization logic to maximize cache hits.

## Phase 3: Financial & Safety Guardrails
- [ ] **Token Tracker**: Implement a middleware or service to track token usage per `run_id`.
- [ ] **Hard Circuit Breaker**: Add logic to `backend/services/run_service.py` to terminate runs exceeding a `MAX_TOKENS_PER_RUN` threshold.
- [ ] **Failover Router**: Implement `FailoverRouter` to switch models/providers on 429 or 500 errors.

## Success Metrics
- [ ] Reduction in total token cost by >50%.
- [ ] Reduction in external tool API calls (Tavily/Firecrawl) by >30% via caching.
- [ ] Zero "Token Drain" incidents (unbounded loops).
