"""
`reap_orphaned_runs` is what rescues a run stuck in a non-terminal state. A
segment task SIGKILLed at the Celery time limit (or a crashed worker) leaves the
run in researching/analyzing/writing forever; a monitor-spawned run whose
auto-advance dispatch was lost hangs at an awaiting_* gate with no human to
approve it. The reaper fails those orphans so they can't linger.

Manual runs parked at an approval gate are a legitimate wait, not an orphan, and
must be left alone.
"""
import uuid
import pytest
import database
from datetime import datetime, timezone
from database import AsyncSessionLocal
from models import Run, RunStatus, Monitor
from config import settings
import services.run_service as run_service


@pytest.fixture(autouse=True)
async def _fresh_engine_pool(monkeypatch):
    # Same rationale as test_run_service_hitl: the module-level AsyncSessionLocal
    # pool's asyncpg connections don't survive a fresh per-test event loop.
    await database.engine.dispose()
    # emit() publishes to Redis; the reaper's UI notification is best-effort, so
    # stub it out to keep these tests DB-only.
    async def _noop_emit(*a, **k):
        return None
    monkeypatch.setattr(run_service, "emit", _noop_emit)
    yield


async def _make_run(db, **overrides) -> Run:
    fields = dict(
        id=uuid.uuid4(), user_id="test_user", topic="t", format="report",
        vertical=None, doc_paths=[], status=RunStatus.pending,
    )
    fields.update(overrides)
    run = Run(**fields)
    db.add(run)
    await db.commit()
    return run


def _force_reap_now(monkeypatch):
    # Negative timeout → cutoff is in the future, so every run's updated_at counts
    # as stale without having to backdate rows past the ORM's onupdate hook.
    monkeypatch.setattr(settings, "RUN_STUCK_TIMEOUT_MIN", -1)


@pytest.mark.asyncio
async def test_reaps_stuck_active_run(monkeypatch):
    _force_reap_now(monkeypatch)
    async with AsyncSessionLocal() as db:
        run = await _make_run(db, status=RunStatus.researching)
        run_id = run.id

    reaped = await run_service.reap_orphaned_runs()

    assert str(run_id) in reaped
    async with AsyncSessionLocal() as db:
        run = await db.get(Run, run_id)
        assert run.status == RunStatus.failed
        assert run.failed_at_status == RunStatus.researching
        assert "reaped" in (run.error_message or "").lower()


@pytest.mark.asyncio
async def test_leaves_manual_gate_untouched(monkeypatch):
    _force_reap_now(monkeypatch)
    async with AsyncSessionLocal() as db:
        # monitor_id is None → a human is expected at this gate.
        run = await _make_run(db, status=RunStatus.awaiting_analysis_approval)
        run_id = run.id

    reaped = await run_service.reap_orphaned_runs()

    assert str(run_id) not in reaped
    async with AsyncSessionLocal() as db:
        run = await db.get(Run, run_id)
        assert run.status == RunStatus.awaiting_analysis_approval


@pytest.mark.asyncio
async def test_reaps_autonomous_gate(monkeypatch):
    _force_reap_now(monkeypatch)
    async with AsyncSessionLocal() as db:
        monitor = Monitor(
            id=uuid.uuid4(), user_id="test_user", name="w", topic="t",
            format="report", interval_minutes=60,
            next_run_at=datetime.now(timezone.utc),
        )
        db.add(monitor)
        await db.commit()
        # Monitor-spawned run parked at a gate with no human → orphan.
        run = await _make_run(
            db, status=RunStatus.awaiting_research_approval, monitor_id=monitor.id
        )
        run_id = run.id

    reaped = await run_service.reap_orphaned_runs()

    assert str(run_id) in reaped
    async with AsyncSessionLocal() as db:
        run = await db.get(Run, run_id)
        assert run.status == RunStatus.failed
        assert run.failed_at_status == RunStatus.awaiting_research_approval


@pytest.mark.asyncio
async def test_does_not_reap_recent_or_terminal_runs(monkeypatch):
    # Large timeout → cutoff far in the past → nothing is stale.
    monkeypatch.setattr(settings, "RUN_STUCK_TIMEOUT_MIN", 10_000)
    async with AsyncSessionLocal() as db:
        active = await _make_run(db, status=RunStatus.writing)
        active_id = active.id

    # Even with the cutoff forced to "now", a terminal run is never reapable.
    monkeypatch.setattr(settings, "RUN_STUCK_TIMEOUT_MIN", -1)
    async with AsyncSessionLocal() as db:
        done = await _make_run(db, status=RunStatus.complete)
        failed = await _make_run(db, status=RunStatus.failed)
        done_id, failed_id = done.id, failed.id

    # Re-widen so the recent active run isn't stale either.
    monkeypatch.setattr(settings, "RUN_STUCK_TIMEOUT_MIN", 10_000)
    reaped = await run_service.reap_orphaned_runs()

    assert reaped == []
    async with AsyncSessionLocal() as db:
        assert (await db.get(Run, active_id)).status == RunStatus.writing
        assert (await db.get(Run, done_id)).status == RunStatus.complete
        assert (await db.get(Run, failed_id)).status == RunStatus.failed
