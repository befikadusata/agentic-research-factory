# TODO

## P0: Spec Finalization
- [x] Resolve remaining doc inconsistencies and freeze v1 spec.
- [x] Add a `Decisions` section (auth flow, model abstraction, run lifecycle).
- Deliverable: locked spec + changelog.

## P0: Backend Skeleton
- [x] Implement `backend/main.py`, `backend/config.py`, `backend/database.py`, `backend/models.py`, `backend/schemas.py`.
- [x] Add startup health, CORS, and environment validation.
- Deliverable: app boots and `GET /health` passes.

## P0: Auth End-to-End
- [x] Implement `backend/auth.py` with `BACKEND_JWT_SECRET` verification.
- [x] Implement `frontend/app/api/backend-token/route.ts`.
- [x] Wire bearer header in `frontend/lib/api.ts`.
- [x] Protect `POST /runs`, `GET /runs`, `GET /runs/{id}`, `POST /runs/{id}/approve`.
- Deliverable: authenticated user can only access their own runs.

## P0: Run Lifecycle + HITL
- [x] Build `backend/services/run_service.py` with queue emitters and HITL event map.
- [x] Implement status transitions: `pending -> researching -> awaiting_hitl -> writing -> complete/failed`.
- [x] Ensure crew kickoff runs off the event loop (`asyncio.to_thread`).
- Deliverable: full run completes with pause/resume.

## P0: Upload + RAG Pathing
- [x] Implement `/upload` storage under `/tmp/research_factory_uploads`.
- [x] Convert `doc_ids` to absolute paths at run creation.
- [x] Parse docs and ingest to in-memory RAG.
- Deliverable: uploaded PDF content is searchable in research task.

## P0: Output Delivery
- [x] Implement markdown and PDF output endpoints.
- [x] Add temp-file cleanup via `BackgroundTask`.
- Deliverable: PDF/MD downloads work repeatedly without leaks.

## P1: Frontend Core UX
- [x] Build dashboard (last 10 runs), new run form, and run detail page.
- [x] Build SSE stream log panel, HITL modal, and output panel.
- [x] Add error/loading/empty states.
- Deliverable: full happy path from topic -> HITL -> output.

## P1: Reliability Hardening
- [x] Add structured logs and request IDs.
- [x] Add retries/timeouts for Tavily, Firecrawl, and LLM calls.
- [x] Add graceful fallback messages.
- Deliverable: predictable failures and debuggable traces.

## P1: Tests
- [x] Add backend API tests for auth, ownership, status transitions, HITL approve, and outputs.
- [x] Add frontend smoke tests for the core flow.
- Deliverable: CI test run and badge.

## P1: Deployment
- [x] Deploy frontend (Vercel), backend (Railway), and DB (Postgres).
- [x] Set envs, production CORS, and a secret-rotation checklist.
- Deliverable: live URL and deployment doc.

## P2: Metrics/Evals
- [x] Implement structured metric collection (latency, citations, LLM-as-Judge).
- [x] Add `/analytics/metrics` endpoint for aggregated insights.
- [x] Create a 20-topic eval set.
- Deliverable: measurable proof of quality.

## P2: Portfolio Assets
- [x] Create architecture diagram.
- [ ] Record a 2-3 minute Loom demo.
- [x] Write two case studies with problem/solution/metrics.
- [ ] Draft Upwork portfolio writeup.
- Deliverable: client-facing asset pack.

## Execution Order
1. [x] Complete P0 items (Spec Finalization through Output Delivery).
2. [x] Complete P1 items (Frontend Core UX through Deployment).
3. [x] Complete P2 items (Metrics/Evals and Portfolio Assets).

## 1-Week Demo Readiness Sprint (Upwork/Portfolio)

### Day 1: Production Deploy Baseline
- [ ] Deploy frontend to Vercel.
- [ ] Deploy backend to Railway/Render.
- [ ] Provision managed Postgres and run migrations.
- [ ] Set production environment variables across frontend/backend.
- [ ] Verify end-to-end flow in production:
  create run -> awaiting_hitl -> approve -> complete -> PDF/MD download.
- Deliverables:
  - [ ] Live app URL.
  - [x] `docs/deployment.md` with setup and access notes.

### Day 2: Reliability + Failure UX
- [x] Implement graceful fallback messages for Tavily failures.
- [x] Implement graceful fallback messages for Firecrawl failures.
- [x] Implement graceful fallback messages for LLM/eval failures.
- [x] Ensure failures surface clearly in SSE logs and UI state.
- [x] Validate timeout/retry behavior for external dependencies.
- Deliverables:
  - [x] `docs/reliability.md` with known failure modes and expected behavior.

### Day 3: Frontend Smoke Tests + CI
- [x] Add frontend smoke tests for core path:
  auth/session mock -> create run -> stream status -> HITL approve -> output panel render.
- [x] Ensure backend tests + frontend tests run in CI on push/PR.
- [x] Add CI badge to `README.md`.
- Deliverables:
  - [x] Green CI workflow.
  - [ ] Test summary section in `README.md`.

### Day 4: Eval Set + Benchmark Run
- [x] Create fixed 20-topic eval set (mixed technical/business topics).
- [ ] Run benchmark using the eval set in a controlled environment.
- [ ] Capture latency, citation count, judge scores, and completion rate.
- [ ] Summarize strengths/weaknesses from results.
- Deliverables:
  - [x] `docs/eval_set.md`
  - [ ] `docs/eval_results.md`

### Day 5: Portfolio Assets
- [x] Create architecture diagram (system + run lifecycle + HITL checkpoint).
- [ ] Record 2-3 minute Loom demo showing one full run.
- [x] Write case study #1 (research report flow + outcomes).
- [x] Write case study #2 (lead intel flow + outcomes).
- Deliverables:
  - [x] `docs/portfolio/architecture.md`
  - [x] `docs/portfolio/case_study_1.md`
  - [x] `docs/portfolio/case_study_2.md`
  - [ ] `docs/portfolio/loom_link.md`

### Day 6: Upwork Packaging
- [x] Draft Upwork portfolio writeup focused on client outcomes.
- [ ] Prepare screenshots/GIFs for dashboard, run detail, HITL modal, outputs.
- [x] Draft FAQ (timeline, cost profile, customization, privacy/data handling).
- Deliverables:
  - [x] `docs/portfolio/upwork_writeup.md`
  - [ ] `docs/portfolio/media/` (screenshots/GIFs)
  - [x] `docs/portfolio/faq.md`

### Day 7: Final QA + Release
- [ ] Run fresh-environment setup using only documented steps.
- [ ] Fix onboarding/documentation mismatches.
- [ ] Final UX pass for loading/empty/error states.
- [ ] Add `docs/demo_readiness_checklist.md`
- [ ] Tag release `demo-ready-v1`.
- Deliverables:
  - [ ] `docs/demo_readiness_checklist.md`
  - [ ] Git tag: `demo-ready-v1`

## Demo Acceptance Criteria
1. [ ] Public live URL works end-to-end without manual intervention.
2. [x] Graceful degradation is verified (e.g. invalid Tavily key does not crash the app).
3. [x] Vertical input UX is intuitive and validation works.
4. [ ] At least 10 runs complete successfully using the eval set.
5. [ ] Portfolio assets (video + case studies + architecture + upwork draft) are published and ready for client delivery.

## The Final Act: Demo-Ready Checklist

### 1. Production Deployment
- [ ] Deploy frontend to Vercel.
- [ ] Deploy backend to Railway/Render.
- [ ] Provision managed Postgres DB and run migrations.
- [ ] Configure production environment variables (API keys, CORS, secrets).
- [ ] Verify end-to-end flow on live URL (create run -> HITL -> PDF download).

### 2. Benchmarking & Quality Proof
- [ ] Execute `docs/scripts/run_eval_set.py` across 20 test topics.
- [ ] Analyze results using LLM-as-a-judge.
- [ ] Summarize strengths/weaknesses and populate `docs/eval_results.md`.

### 3. Visual Portfolio Assets
- [ ] Record a 2-3 minute Loom demo showing the full end-to-end flow.
- [ ] Capture high-quality UI screenshots/GIFs (dashboard, vertical selector, SSE logs, HITL modal).
- [ ] Save visual assets to `docs/portfolio/media/`.

### 4. Final QA & Release
- [ ] Run fresh-environment setup test using only `README.md` to ensure onboarding is flawless.
- [ ] Fix onboarding/documentation mismatches.
- [ ] Final UX pass for loading/empty/error states.
- [ ] Add test summary section in `README.md`.
- [ ] Add `docs/demo_readiness_checklist.md` (or finalize this list).
- [ ] Cut the `demo-ready-v1` Git release tag.

### 5. Vertical Mapping Fixes (Missing/Partial Implementation)
- [ ] Backend: Implement and test missing validation for required `vertical_inputs`.
- [ ] Backend: Add test to confirm task routing (`lead_intel` vs `research_report`).
- [ ] Frontend: Update smoke test to verify `vertical_inputs` payload is correctly submitted.
- [ ] Frontend: Show compact submitted vertical input brief on run detail page (Optional).

## Vertical Mapping Implementation (Generic Core + 3 Playbooks)

### Scope
- [x] Keep core pipeline generic and unchanged (ingest -> research -> HITL -> analyze -> write/edit -> export).
- [x] Add verticalized behavior via config and input mapping only.
- [x] Support 3 verticals:
  - [x] `b2b_sales_lead_intel`
  - [x] `marketing_competitor_briefs`
  - [x] `founder_strategy_briefs`

### Backend: Data Model + API
- [x] Extend `CreateRunRequest` with:
  - [x] `vertical: str`
  - [x] `vertical_inputs: dict`
  - File: `backend/schemas.py`
- [x] Persist vertical fields in `Run` model:
  - [x] `vertical` (string)
  - [x] `vertical_inputs` (JSON)
  - File: `backend/models.py`
- [x] Create DB migration for new columns:
  - [x] `runs.vertical`
  - [x] `runs.vertical_inputs`
  - Path: `backend/migrations/`
- [x] Pass through fields during run creation.
  - File: `backend/routers/runs.py`

### Backend: Vertical Registry + Resolution
- [x] Add vertical config registry.
  - Suggested file: `backend/configs/verticals.py`
- [x] Define per-vertical:
  - [x] input schema (required/optional fields)
  - [x] prompt focus
  - [x] output sections
  - [x] quality rubric
  - [x] vertical metric keys
- [x] In run execution, resolve vertical config and build `execution_brief` from:
  - [x] topic
  - [x] vertical inputs
  - [x] vertical research/analysis focus
  - File: `backend/services/run_service.py`
- [x] Attach vertical metadata in metrics output (`vertical`, `vertical_kpis` placeholder).
  - File: `backend/services/run_service.py`

### Backend: Agent Prompt Injection (No Graph Rewrite)
- [x] Keep supervisor graph structure unchanged.
  - File: `backend/agents/crew.py`
- [x] Inject vertical playbook instructions into task descriptions:
  - [x] `backend/agents/researcher.py`
  - [x] `backend/agents/analyst.py`
  - [x] `backend/agents/writer.py`
  - [x] `backend/agents/editor.py`
  - [x] `backend/agents/lead_intel.py`
- [x] Ensure writer/editor enforce vertical-specific output sections.

### Frontend: Vertical-First Run Creation
- [x] Add vertical selector (3 cards) on new run page.
  - File: `frontend/app/new/page.tsx`
- [x] Render dynamic fields based on selected vertical input schema.
  - File: `frontend/app/new/page.tsx`
- [x] Extend client types for verticals and vertical payload.
  - File: `frontend/lib/types.ts`
- [x] Extend `createRun` payload with `vertical` + `vertical_inputs`.
  - File: `frontend/lib/api.ts`
- [x] Decide format behavior:
  - [x] Map default format per vertical, or
  - [x] Keep manual format override in UI.
  - File: `frontend/components/FormatSelector.tsx` + `frontend/app/new/page.tsx`

### Frontend: Run Detail Context
- [x] Display selected vertical in run header.
  - File: `frontend/app/runs/[id]/page.tsx`
- [x] Optional: show compact submitted vertical input brief.
  - File: `frontend/app/runs/[id]/page.tsx`

### Tests
- [x] Backend:
  - [x] Reject unknown vertical
  - [ ] Validate required `vertical_inputs` (Not implemented/tested)
  - [ ] Confirm task routing (`lead_intel` for sales, `research_report` for others) (Not tested)
  - Files: `backend/tests/`
- [x] Frontend smoke:
  - [x] Vertical select -> dynamic fields render
  - [ ] Submit includes vertical payload (Partially implemented: ignores vertical_inputs)
  - Files: frontend test suite path (to be added)


## P5: Complex HITL (Multi-stage Approval)
- [ ] Define multi-stage `RunStatus` (e.g., `awaiting_research_approval`, `awaiting_analysis_approval`, `awaiting_final_approval`).
- [ ] Create `Approval` model in `models.py` to track history of approvals/rejections by stage.
- [ ] Update `backend/services/run_service.py` to support branching logic for multiple HITL checkpoints.
- [ ] Update API `approve_hitl` to handle `stage` parameter.
- [ ] Update Frontend `HitlModal` to show current stage and allow feedback/rejection.
- [ ] Update E2E tests for multi-stage workflow.
