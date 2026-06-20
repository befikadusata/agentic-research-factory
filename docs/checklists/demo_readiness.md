# Demo Readiness Checklist

## Pre-Deploy
- [ ] All backend tests pass locally (`cd backend && pytest`)
- [ ] Frontend lints clean (`cd frontend && npm run lint`)
- [ ] Frontend builds without errors (`cd frontend && npm run build`)
- [ ] Docker Compose stack boots (`docker compose up`)
- [ ] `GET /health` returns `{"status": "ok"}`

## Deploy
- [ ] Database provisioned with pgvector
- [ ] Backend deployed (Railway/Render)
- [ ] Frontend deployed (Vercel)
- [ ] Environment variables set per `docs/deployment.md`
- [ ] CORS configured for production domain
- [ ] OAuth callback URL updated

## End-to-End Verification
- [ ] Sign in works via Google OAuth
- [ ] Create run (general, no vertical) → completes → PDF downloads
- [ ] Create run (B2B Sales Lead Intel) → completes → dossier has all sections
- [ ] Create run (Marketing Competitor Brief) → HITL → approve → completes
- [ ] Create run (Founder Strategy Brief) → completes → has required sections
- [ ] SSE stream shows real-time agent logs
- [ ] HITL modal shows research summary and accepts instructions
- [ ] Dashboard shows last 10 runs
- [ ] Error state displays correctly (trigger by using invalid API key)

## Documentation
- [ ] `README.md` is current with setup instructions
- [ ] `docs/deployment.md` matches actual deploy steps
- [ ] `docs/reliability.md` covers known failure modes
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
