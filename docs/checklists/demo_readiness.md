# Demo Readiness Checklist

## Pre-Deploy
- [ ] Backend tests pass locally (`cd backend && uv run pytest`) — the project is uv-managed (`pyproject.toml` + `uv.lock`), and CI runs `uv run pytest`
- [ ] Migrations apply cleanly (`cd backend && uv run alembic upgrade head`)
- [ ] Frontend lints clean (`cd frontend && npm run lint`)
- [ ] Frontend builds without errors (`cd frontend && npm run build`)
- [ ] Frontend e2e passes (`cd frontend && npm run test:e2e`) — it boots its own `next dev` on port 3200 (`reuseExistingServer: false`), so a stale server on 3000 is neither used nor a blocker
- [ ] Docker Compose stack boots (`docker compose up --build`)
- [ ] `GET /health` returns 200 with `{"status": "ok", "db": "ok", "redis": "ok"}` — it probes Postgres and Redis with a 2s timeout each and returns 503 `"degraded"` if either fails

## Deploy
- [ ] Database provisioned with pgvector
- [ ] Backend deployed (Railway/Render)
- [ ] Frontend deployed (Vercel)
- [ ] Environment variables set per [`../deployment.md`](../deployment.md)
- [ ] `BACKEND_JWT_SECRET` is identical on both sides and is not a shipped dev value (`validate_config` rejects those in production, min 32 chars)
- [ ] CORS configured for the production domain (`FRONTEND_URL` — the backend allows exactly that one origin)
- [ ] OAuth callback URL updated
- [ ] Object storage configured for uploads — the API and the Celery worker are separate containers, so a local upload path only works when they share a filesystem

## End-to-End Verification

Approval gates are set by **task type**, not by vertical. `research_report`
(everything except B2B Sales Lead Intel) pauses at three gates — research,
analysis, final. `lead_intel` pauses at one — final. Only monitor-spawned runs
auto-advance through gates.

- [ ] Sign in via Google OAuth
- [ ] Sign in via email + password (`credentials` provider), including the verification-email path
- [ ] Create run (general, no vertical) → approve 3 gates → completes → PDF downloads
- [ ] Create run (B2B Sales Lead Intel) → approve the final gate → dossier has all sections
- [ ] Create run (Marketing Competitor Brief) → approve 3 gates → completes
- [ ] Create run (Founder Strategy Brief) → approve 3 gates → completes → has required sections
- [ ] SSE stream shows real-time agent logs, and a heartbeat holds the connection open through a quiet stretch
- [ ] HITL modal shows the stage summary and accepts instructions; the next stage reflects them
- [ ] Dashboard lists runs (`GET /runs` defaults to 20, max 100)
- [ ] Sources panel flags unverified citations
- [ ] Error state displays correctly — the UI renders the backend's raw message verbatim as `Run failed: …`, so trigger it with an invalid provider API key and confirm the message is legible
- [ ] A monitor fires on its interval, produces a diff, and delivers its alert (webhook or email)

## Documentation
- [ ] `README.md` is current with setup instructions
- [ ] [`../deployment.md`](../deployment.md) matches actual deploy steps
- [ ] [`../reliability.md`](../reliability.md) covers known failure modes
- [ ] CI badge shows in README

## Portfolio Assets
- [ ] Architecture diagram created
- [ ] Loom demo recorded (2–3 min)
- [ ] Case studies written (2)
- [ ] Upwork writeup ready
- [ ] FAQ complete
- [ ] Screenshots/GIFs captured

## Release
- [ ] Git tag: `demo-ready-v1`
