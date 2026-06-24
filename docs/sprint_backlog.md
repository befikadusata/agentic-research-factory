# Sprint Backlog

This backlog is organized for handoff of an unfinished project. It prioritizes foundation first, then core product flow, then product quality and release readiness.

## Sprint 0: Project Setup and Release Foundation

- Goal: make the repo easy to run, test, and ship consistently.
- Scope:
  - Docker Compose for the full stack.
  - Backend and frontend environment templates.
  - GitHub Actions CI.
  - Alembic migration flow.
  - Basic config validation and secrets handling.
  - Local dev and deployment docs alignment.
- Key files:
  - [docker-compose.yml](/home/befikadusata/Devs/2026/agentic-research-factory/docker-compose.yml)
  - [backend/Dockerfile](/home/befikadusata/Devs/2026/agentic-research-factory/backend/Dockerfile)
  - [frontend/Dockerfile](/home/befikadusata/Devs/2026/agentic-research-factory/frontend/Dockerfile)
  - [backend/alembic/](/home/befikadusata/Devs/2026/agentic-research-factory/backend/alembic)
  - [README.md](/home/befikadusata/Devs/2026/agentic-research-factory/README.md)
- Done when:
  - `docker compose up --build` boots the app end-to-end.
  - CI runs backend tests and frontend checks on every PR.
  - New contributors can follow one setup path without guessing.

## Sprint 1: Identity, Auth, and Access Control

- Goal: lock down the app so all later work is built on real user identity.
- Scope:
  - Google sign-in flow.
  - Backend user extraction and request auth.
  - Route protection on runs, uploads, outputs, and workspaces.
  - Workspace membership enforcement.
- Key files:
  - [backend/auth.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/auth.py)
  - [frontend/app/api/auth/[...nextauth]/route.ts](/home/befikadusata/Devs/2026/agentic-research-factory/frontend/app/api/auth/[...nextauth]/route.ts)
  - [frontend/lib/auth.ts](/home/befikadusata/Devs/2026/agentic-research-factory/frontend/lib/auth.ts)
  - [backend/routers/workspaces.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/routers/workspaces.py)
- Done when:
  - Unauthenticated users cannot create or view runs.
  - Users only see their own runs or workspace-authorized runs.
  - Workspace owner/member permissions work predictably.

## Sprint 2: Core Data Model and Run Lifecycle

- Goal: make the product's core business object, the run, reliable and inspectable.
- Scope:
  - Run schema completion.
  - Status transitions.
  - Persistence of topic, format, vertical, outputs, logs, and costs.
  - Run list and run detail APIs.
- Key files:
  - [backend/models.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/models.py)
  - [backend/routers/runs.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/routers/runs.py)
  - [backend/services/run_service.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/services/run_service.py)
  - [backend/schemas.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/schemas.py)
- Done when:
  - A run can be created, fetched, and listed consistently.
  - Status changes are persisted and reflected in the UI.
  - Failed runs are visible and diagnosable.

## Sprint 3: Upload and Ingestion Pipeline

- Goal: allow users to attach source documents and make them usable by the research engine.
- Scope:
  - PDF upload validation and storage.
  - Parsing PDFs into chunks.
  - Indexing docs into the retrieval layer.
  - Workspace-scoped document collections.
- Key files:
  - [backend/routers/upload.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/routers/upload.py)
  - [backend/services/pdf_service.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/services/pdf_service.py)
  - [backend/tools/rag.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/tools/rag.py)
- Done when:
  - PDF upload rejects invalid files.
  - Good PDFs are ingested and available to runs.
  - Retrieval can use uploaded material as context.

## Sprint 4: Retrieval Quality and Evidence Generation

- Goal: make the research output trustworthy enough for real use.
- Scope:
  - Query rewriting.
  - Hybrid retrieval.
  - Re-ranking.
  - Citation handling.
  - Workspace filtering in retrieval.
- Key files:
  - [backend/services/query_rewriter.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/services/query_rewriter.py)
  - [backend/tools/search.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/tools/search.py)
  - [backend/tools/rag.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/tools/rag.py)
- Done when:
  - Retrieval returns relevant evidence, not noisy chunks.
  - Users can trace claims back to source material.
  - Docs from one workspace do not leak into another.

## Sprint 5: Agent Orchestration

- Goal: make the multi-agent pipeline behave deterministically enough to support product workflows.
- Scope:
  - Supervisor routing.
  - Research, analysis, writing, editing, and lead-intel paths.
  - Retry and fallback logic.
  - Task-type routing for verticals.
- Key files:
  - [backend/agents/crew.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/agents/crew.py)
  - [backend/agents/](/home/befikadusata/Devs/2026/agentic-research-factory/backend/agents)
- Done when:
  - Each task type follows the intended path.
  - Retry behavior is predictable.
  - The pipeline can be debugged from logs and run state.

## Sprint 6: Human-in-the-Loop Review

- Goal: make review checkpoints a real product feature, not a partial demo.
- Scope:
  - Pause states.
  - Approval endpoint.
  - Instruction injection into the next stage.
  - Resume handling after approval.
- Key files:
  - [backend/routers/hitl.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/routers/hitl.py)
  - [backend/services/run_service.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/services/run_service.py)
  - [frontend/components/HitlModal.tsx](/home/befikadusata/Devs/2026/agentic-research-factory/frontend/components/HitlModal.tsx)
- Done when:
  - The run pauses at review points.
  - The user can approve with or without extra direction.
  - The next stage incorporates that feedback.

## Sprint 7: Real-Time Streaming and Run Observability

- Goal: let users watch the system work in real time.
- Scope:
  - Redis pub/sub event emission.
  - SSE streaming endpoint.
  - Frontend log consumption.
  - Status synchronization in the UI.
- Key files:
  - [backend/routers/stream.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/routers/stream.py)
  - [backend/services/run_service.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/services/run_service.py)
  - [frontend/app/runs/[id]/page.tsx](/home/befikadusata/Devs/2026/agentic-research-factory/frontend/app/runs/[id]/page.tsx)
- Done when:
  - Logs stream live.
  - Status updates appear without page refresh.
  - Completion and error events close out the stream cleanly.

## Sprint 8: Output Generation and Delivery

- Goal: turn completed runs into usable deliverables.
- Scope:
  - Markdown rendering.
  - PDF export.
  - Download endpoints.
  - Final output formatting cleanup.
- Key files:
  - [backend/routers/outputs.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/routers/outputs.py)
  - [backend/services/pdf_service.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/services/pdf_service.py)
  - [frontend/components/OutputPanel.tsx](/home/befikadusata/Devs/2026/agentic-research-factory/frontend/components/OutputPanel.tsx)
- Done when:
  - Completed runs expose `.md` and `.pdf`.
  - Output is readable and formatted well.
  - Download links work from the run page.

## Sprint 9: Frontend Workflow Completion

- Goal: make the UI a complete workflow from sign-in to final deliverable.
- Scope:
  - Landing page.
  - New run form.
  - Vertical selector.
  - Upload flow.
  - Run list and run detail UX.
- Key files:
  - [frontend/app/page.tsx](/home/befikadusata/Devs/2026/agentic-research-factory/frontend/app/page.tsx)
  - [frontend/app/new/page.tsx](/home/befikadusata/Devs/2026/agentic-research-factory/frontend/app/new/page.tsx)
  - [frontend/components/FileUpload.tsx](/home/befikadusata/Devs/2026/agentic-research-factory/frontend/components/FileUpload.tsx)
  - [frontend/components/RunCard.tsx](/home/befikadusata/Devs/2026/agentic-research-factory/frontend/components/RunCard.tsx)
  - [frontend/components/VerticalSelector.tsx](/home/befikadusata/Devs/2026/agentic-research-factory/frontend/components/VerticalSelector.tsx)
- Done when:
  - A user can create a run without confusion.
  - The detail page explains status, progress, and output clearly.
  - Empty and error states are usable.

## Sprint 10: Vertical Playbooks

- Goal: turn the app from generic research into distinct business workflows.
- Scope:
  - Vertical-specific inputs.
  - Prompt focus and required sections.
  - Format defaults.
  - Output quality rubric per playbook.
- Key files:
  - [backend/configs/verticals.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/configs/verticals.py)
  - [frontend/lib/types.ts](/home/befikadusata/Devs/2026/agentic-research-factory/frontend/lib/types.ts)
- Done when:
  - Each playbook generates meaningfully different outputs.
  - Required fields are enforced.
  - The UI and backend stay in sync on vertical definitions.

## Sprint 11: Analytics, Cost, and Evaluation

- Goal: make the system measurable so regressions are visible.
- Scope:
  - Cost tracking.
  - Run metrics aggregation.
  - Evaluation endpoints or services.
  - Benchmark dataset and score reporting.
- Key files:
  - [backend/routers/analytics.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/routers/analytics.py)
  - [backend/services/eval_service.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/services/eval_service.py)
  - [backend/utils/cost_tracker.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/utils/cost_tracker.py)
  - [backend/tests/test_benchmark.py](/home/befikadusata/Devs/2026/agentic-research-factory/backend/tests/test_benchmark.py)
- Done when:
  - You can answer "how much did this run cost?" and "how good was it?"
  - Evaluation results are repeatable.
  - Metrics are visible for completed runs.

## Sprint 12: Hardening and Release Readiness

- Goal: make the project handoff-safe.
- Scope:
  - Backend tests.
  - Frontend smoke and e2e tests.
  - Timeout and retry behavior.
  - Deployment docs.
  - Observability and logging cleanup.
- Key files:
  - [backend/tests/](/home/befikadusata/Devs/2026/agentic-research-factory/backend/tests)
  - [frontend/e2e/smoke.spec.ts](/home/befikadusata/Devs/2026/agentic-research-factory/frontend/e2e/smoke.spec.ts)
  - [docs/deployment.md](/home/befikadusata/Devs/2026/agentic-research-factory/docs/deployment.md)
  - [docs/reliability.md](/home/befikadusata/Devs/2026/agentic-research-factory/docs/reliability.md)
- Done when:
  - CI is green.
  - Critical flows have automated coverage.
  - Production failure modes are understood and documented.

## Recommended Execution Order

1. Sprint 0
2. Sprint 1
3. Sprint 2
4. Sprint 3
5. Sprint 4
6. Sprint 5
7. Sprint 6
8. Sprint 7
9. Sprint 8
10. Sprint 9
11. Sprint 10
12. Sprint 11
13. Sprint 12
