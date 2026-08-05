import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

import database
from models import Monitor, Run, RunStatus
from services.monitor_service import _send_webhook, finalize_monitored_run


@pytest.fixture
async def fresh_pool():
    """finalize_monitored_run uses the module-level AsyncSessionLocal (on
    database.engine), whose pooled asyncpg connections don't survive
    pytest-asyncio's per-test event loop. Dispose so it gets a fresh,
    loop-bound connection — same pattern as test_run_service_hitl."""
    await database.engine.dispose()
    yield
    await database.engine.dispose()


def _payload(**over):
    base = {
        "name": "Nvidia watch",
        "topic": "Nvidia earnings and guidance",
        "format": "report",
    }
    base.update(over)
    return base


@pytest.mark.asyncio
async def test_create_monitor(client, mock_user):
    r = await client.post("/monitors", json=_payload())
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Nvidia watch"
    assert data["user_id"] == mock_user
    assert data["enabled"] is True
    assert data["interval_minutes"] == 1440
    assert data["last_run_id"] is None
    assert "next_run_at" in data


@pytest.mark.asyncio
async def test_create_monitor_requires_auth(client):
    r = await client.post("/monitors", json=_payload())
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_monitor_unknown_vertical_rejected(client, mock_user):
    r = await client.post("/monitors", json=_payload(vertical="not_a_vertical"))
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_monitor_interval_bounds_enforced(client, mock_user):
    assert (await client.post("/monitors", json=_payload(interval_minutes=5))).status_code == 422
    assert (await client.post("/monitors", json=_payload(interval_minutes=15))).status_code == 201


@pytest.mark.asyncio
async def test_list_monitors_returns_own_not_others(client, auth_as, db_session):
    other = Monitor(user_id="someone-else", name="Theirs", topic="AMD watch",
                    format="report", interval_minutes=60,
                    next_run_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
    db_session.add(other)
    await db_session.commit()

    auth_as("test-user-123")
    await client.post("/monitors", json=_payload(name="Mine"))
    r = await client.get("/monitors")
    assert r.status_code == 200
    names = {m["name"] for m in r.json()}
    assert "Mine" in names
    assert "Theirs" not in names


@pytest.mark.asyncio
async def test_get_monitor_404_for_non_owner(client, auth_as, db_session):
    import datetime as dt
    other = Monitor(user_id="someone-else", name="Theirs", topic="AMD watch",
                    format="report", interval_minutes=60,
                    next_run_at=dt.datetime.now(dt.UTC))
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    auth_as("test-user-123")
    r = await client.get(f"/monitors/{other.id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_monitor_toggle_and_interval(client, mock_user):
    created = (await client.post("/monitors", json=_payload(enabled=False))).json()
    mid = created["id"]

    r = await client.patch(f"/monitors/{mid}", json={"enabled": True, "interval_minutes": 120})
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] is True
    assert data["interval_minutes"] == 120


@pytest.mark.asyncio
async def test_run_monitor_now_spawns_linked_run(client, mock_user, db_session):
    created = (await client.post("/monitors", json=_payload())).json()
    mid = created["id"]

    r = await client.post(f"/monitors/{mid}/run")
    assert r.status_code == 201
    run_id = r.json()["id"]
    # Serialized, not just stored: the UI distinguishes a monitored run from a
    # one-off by this field, and offers "save as monitor" only for the latter.
    assert r.json()["monitor_id"] == mid

    run = await db_session.get(Run, UUID(run_id))
    assert str(run.monitor_id) == mid
    monitor = await db_session.get(Monitor, UUID(mid))
    assert str(monitor.last_run_id) == run_id

    hist = await client.get(f"/monitors/{mid}/runs")
    assert hist.status_code == 200
    assert run_id in {r["id"] for r in hist.json()}
    assert all(r["monitor_id"] == mid for r in hist.json())


@pytest.mark.asyncio
async def test_delete_monitor_detaches_runs(client, mock_user, db_session):
    created = (await client.post("/monitors", json=_payload())).json()
    mid = created["id"]
    run_id = (await client.post(f"/monitors/{mid}/run")).json()["id"]

    r = await client.delete(f"/monitors/{mid}")
    assert r.status_code == 204

    # Monitor gone, but its run survives with monitor_id detached (SET NULL).
    assert await db_session.get(Monitor, UUID(mid)) is None
    db_session.expire_all()
    run = await db_session.get(Run, UUID(run_id))
    assert run is not None
    assert run.monitor_id is None


# ── finalize_monitored_run (diff + alert) ──────────────────────────────────
# These use AsyncSessionLocal (database.engine) for setup + readback so they
# share one engine with finalize_monitored_run — mixing in the db_session
# fixture's separate engine trips asyncpg's cross-loop/greenlet guards.

async def _make_monitor(**over):
    now = dt.datetime.now(dt.UTC)
    async with database.AsyncSessionLocal() as db:
        m = Monitor(user_id="test-user-123", name="Watch", topic="Nvidia",
                    format="report", interval_minutes=60, next_run_at=now, **over)
        db.add(m)
        await db.commit()
        await db.refresh(m)
        return m


async def _make_run(monitor_id, output, created_at):
    async with database.AsyncSessionLocal() as db:
        r = Run(user_id="test-user-123", topic="Nvidia", format="report",
                status=RunStatus.complete, final_output=output,
                monitor_id=monitor_id, created_at=created_at)
        db.add(r)
        await db.commit()
        await db.refresh(r)
        return r


async def _run_metrics(run_id):
    async with database.AsyncSessionLocal() as db:
        run = await db.get(Run, run_id)
        return run.metrics or {}


@pytest.mark.asyncio
async def test_finalize_noop_for_unmonitored_run(fresh_pool):
    now = dt.datetime.now(dt.UTC)
    run = await _make_run(None, "some output", now)
    with patch("services.monitor_service._diff_runs", new_callable=AsyncMock) as diff:
        await finalize_monitored_run(run.id)
        diff.assert_not_called()
    assert "monitor_diff" not in await _run_metrics(run.id)


@pytest.mark.asyncio
async def test_finalize_baseline_no_previous_run(fresh_pool):
    now = dt.datetime.now(dt.UTC)
    m = await _make_monitor(notify_channel="alerts@example.com")
    run = await _make_run(m.id, "first output", now)

    with patch("services.monitor_service._diff_runs", new_callable=AsyncMock) as diff, \
         patch("services.monitor_service.send_email") as mail:
        await finalize_monitored_run(run.id)
        diff.assert_not_called()   # nothing to compare against
        mail.assert_not_called()   # baseline never alerts

    md = (await _run_metrics(run.id))["monitor_diff"]
    assert md["baseline"] is True and md["changed"] is False


@pytest.mark.asyncio
async def test_finalize_changed_stores_diff_and_alerts(fresh_pool):
    now = dt.datetime.now(dt.UTC)
    m = await _make_monitor(notify_channel="alerts@example.com")
    await _make_run(m.id, "old findings", now - dt.timedelta(hours=2))
    current = await _make_run(m.id, "new findings", now)

    fake_diff = {"changed": True, "summary": "Guidance raised.", "highlights": ["+20% revenue"]}
    with patch("services.monitor_service._diff_runs", new_callable=AsyncMock, return_value=fake_diff), \
         patch("services.monitor_service.send_email") as mail:
        await finalize_monitored_run(current.id)
        mail.assert_called_once()
        assert mail.call_args.args[0] == "alerts@example.com"

    assert (await _run_metrics(current.id))["monitor_diff"] == fake_diff


@pytest.mark.asyncio
async def test_finalize_changed_but_no_channel_skips_alert(fresh_pool):
    now = dt.datetime.now(dt.UTC)
    m = await _make_monitor(notify_channel=None)
    await _make_run(m.id, "old", now - dt.timedelta(hours=2))
    current = await _make_run(m.id, "new", now)

    fake_diff = {"changed": True, "summary": "changed", "highlights": []}
    with patch("services.monitor_service._diff_runs", new_callable=AsyncMock, return_value=fake_diff), \
         patch("services.monitor_service.send_email") as mail:
        await finalize_monitored_run(current.id)
        mail.assert_not_called()


@pytest.mark.asyncio
async def test_finalize_url_channel_routes_to_webhook(fresh_pool):
    now = dt.datetime.now(dt.UTC)
    m = await _make_monitor(notify_channel="https://hooks.example.com/abc")
    await _make_run(m.id, "old", now - dt.timedelta(hours=2))
    current = await _make_run(m.id, "new", now)

    fake_diff = {"changed": True, "summary": "changed", "highlights": ["a"]}
    with patch("services.monitor_service._diff_runs", new_callable=AsyncMock, return_value=fake_diff), \
         patch("services.monitor_service._send_webhook", new_callable=AsyncMock) as hook, \
         patch("services.monitor_service.send_email") as mail:
        await finalize_monitored_run(current.id)
        hook.assert_awaited_once()
        assert hook.await_args.args[0] == "https://hooks.example.com/abc"
        mail.assert_not_called()


@pytest.mark.asyncio
async def test_send_webhook_posts_structured_payload():
    from uuid import uuid4
    run_id = uuid4()
    mock_resp = MagicMock()
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    diff = {"changed": True, "summary": "Guidance raised.", "highlights": ["+20%"]}
    with patch("services.monitor_service.httpx.AsyncClient", return_value=mock_client):
        await _send_webhook("https://hooks.example.com/x", "Nvidia watch", run_id, diff)

    mock_client.post.assert_awaited_once()
    url = mock_client.post.await_args.args[0]
    body = mock_client.post.await_args.kwargs["json"]
    assert url == "https://hooks.example.com/x"
    assert body["run_id"] == str(run_id)
    assert body["diff"] == diff
    assert "Nvidia watch" in body["text"]
    mock_resp.raise_for_status.assert_called_once()
