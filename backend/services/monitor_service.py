"""Saved monitors: scheduling them, and reporting what changed between runs.

`dispatch_due_monitors` is invoked periodically by a Celery-beat task. It finds
monitors whose `next_run_at` has passed, spawns a fresh Run for each (tagged
with `monitor_id`), advances the schedule, and queues the pipeline task.

`finalize_monitored_run` closes the loop from the other end: the run pipeline
calls it on completion, and it diffs the output against the monitor's previous
run and delivers an alert on the monitor's `notify_channel` when something
material changed.
"""
import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from uuid import UUID
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from litellm import acompletion

from database import AsyncSessionLocal
from models import Monitor, Run, RunStatus
from services.run_dispatch import build_run
from services.llm_router import get_completion_settings
from utils.json_parse import parse_json
from utils.email import send_email
from celery_app import execute_run_task
from logger import logger


async def dispatch_due_monitors() -> list[str]:
    """Spawn a run for every monitor whose schedule is due. Returns the ids of
    the runs that were queued. Safe to call repeatedly (idempotent per tick)."""
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        due_ids = (
            await db.execute(
                select(Monitor.id).where(
                    Monitor.enabled.is_(True),
                    Monitor.next_run_at <= now,
                )
            )
        ).scalars().all()

    dispatched: list[str] = []
    for monitor_id in due_ids:
        run_id = await _spawn_monitor_run(monitor_id, now)
        if run_id:
            # Dispatch only after the run + advanced schedule are committed, so a
            # crash can never queue a task for an un-persisted run.
            execute_run_task.delay(run_id)
            dispatched.append(run_id)

    if dispatched:
        logger.info("monitors_dispatched", count=len(dispatched))
    return dispatched


async def _spawn_monitor_run(monitor_id: UUID, now: datetime) -> Optional[str]:
    """Atomically: lock the monitor, create its run, advance `next_run_at`, and
    commit. Returns the new run id, or None if the monitor was grabbed by a
    concurrent dispatcher / disabled in the meantime."""
    async with AsyncSessionLocal() as db:
        # Row-lock so two overlapping dispatch ticks can't both spawn a run for
        # the same monitor — the loser re-reads the advanced next_run_at and bails.
        monitor = (
            await db.execute(
                select(Monitor).where(Monitor.id == monitor_id).with_for_update()
            )
        ).scalar_one_or_none()

        if monitor is None or not monitor.enabled or monitor.next_run_at > now:
            return None

        run = build_run(
            user_id=monitor.user_id,
            topic=monitor.topic,
            format=monitor.format,
            doc_paths=monitor.doc_paths,
            workspace_id=monitor.workspace_id,
            vertical=monitor.vertical,
            vertical_inputs=monitor.vertical_inputs,
            monitor_id=monitor.id,
        )
        db.add(run)
        await db.flush()  # assign run.id before we reference it below

        monitor.next_run_at = now + timedelta(minutes=monitor.interval_minutes)
        monitor.last_run_id = run.id
        monitor.last_run_at = now
        await db.commit()
        return str(run.id)


async def finalize_monitored_run(run_id: UUID) -> None:
    """Diff a just-completed monitored run against the monitor's previous run and
    alert if something changed. Best-effort: called from the run pipeline, so it
    must never raise back into it — a failed diff can't fail the run."""
    try:
        async with AsyncSessionLocal() as db:
            run = await db.get(Run, run_id)
            if run is None or run.monitor_id is None:
                return  # ordinary one-off run — nothing to do
            monitor = await db.get(Monitor, run.monitor_id)

            previous = (
                await db.execute(
                    select(Run)
                    .where(
                        Run.monitor_id == run.monitor_id,
                        Run.id != run.id,
                        Run.status == RunStatus.complete,
                    )
                    .order_by(Run.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

            if previous is None:
                diff = {"baseline": True, "changed": False,
                        "summary": "Baseline run — no prior run to compare against."}
            else:
                diff = await _diff_runs(previous.final_output or "", run.final_output or "", run.topic, run_id=run_id)

            # Capture what the alert needs before commit expires the ORM objects.
            notify_channel = monitor.notify_channel if monitor else None
            monitor_name = monitor.name if monitor else ""

            run.metrics = {**(run.metrics or {}), "monitor_diff": diff}
            flag_modified(run, "metrics")
            await db.commit()

        if diff.get("changed") and notify_channel:
            await _send_alert(notify_channel, monitor_name, run_id, diff)
    except Exception:
        logger.exception("monitor_finalize_failed", run_id=str(run_id))


async def _diff_runs(previous: str, current: str, topic: str, run_id=None) -> dict:
    """LLM change-detection between two versions of a monitored brief. Returns a
    safe fallback dict on any failure rather than raising. This is a direct
    litellm call on a beat schedule; when `run_id` is given its cost is logged to
    run_costs so the monitor's ongoing spend is visible in /analytics/costs."""
    prompt = f"""You are tracking how a research brief on "{topic}" changes between runs.
Compare the PREVIOUS and CURRENT versions and report only what MATERIALLY changed —
new facts, reversals, added or removed findings. Ignore pure rewording.

PREVIOUS:
{previous[:3000]}

CURRENT:
{current[:3000]}

Respond ONLY with valid JSON:
{{"changed": true, "summary": "one short paragraph on what changed", "highlights": ["point", "point"]}}
If nothing material changed, respond {{"changed": false, "summary": "No material changes.", "highlights": []}}."""

    try:
        llm = get_completion_settings("eval")
        response = await acompletion(
            model=llm.model,
            api_key=llm.api_key,
            base_url=llm.base_url,
            fallbacks=list(llm.fallbacks),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            timeout=60,
        )
        if run_id is not None:
            from utils.cost_tracker import log_direct_call
            await log_direct_call(run_id, "monitor_diff", response, routing_agent="eval")
        return parse_json(response.choices[0].message.content)
    except Exception as e:
        logger.warning("monitor_diff_failed", error=str(e))
        return {"changed": False, "summary": "Change detection unavailable.", "error": str(e)}


async def _send_alert(notify_channel: str, monitor_name: str, run_id: UUID, diff: dict) -> None:
    """Deliver a change alert. An http(s) `notify_channel` gets a JSON webhook
    POST (Slack/Discord/automation-friendly); anything with an '@' is emailed."""
    channel = notify_channel.strip()
    if channel.startswith(("http://", "https://")):
        await _send_webhook(channel, monitor_name, run_id, diff)
    elif "@" in channel:
        await _send_email_alert(channel, monitor_name, run_id, diff)
    else:
        logger.info("monitor_alert_unknown_channel", channel=channel)


async def _send_email_alert(to_email: str, monitor_name: str, run_id: UUID, diff: dict) -> None:
    subject = f"[Monitor] Change detected: {monitor_name}"
    highlights = "\n".join(f"- {h}" for h in diff.get("highlights", []))
    body = (
        f"Your monitor '{monitor_name}' detected a change.\n\n"
        f"{diff.get('summary', '')}\n\n"
        f"{highlights}\n\n"
        f"View the run: /runs/{run_id}\n"
    )
    # send_email is synchronous (smtplib); keep it off the event loop.
    await asyncio.to_thread(send_email, to_email, subject, body)


async def _send_webhook(url: str, monitor_name: str, run_id: UUID, diff: dict) -> None:
    """POST the change as JSON. Slack/Discord read `text`; programmatic
    consumers get the structured `monitor`/`run_id`/`diff` fields."""
    highlights = "".join(f"\n• {h}" for h in diff.get("highlights", []))
    payload = {
        "text": f"[Monitor] Change detected: {monitor_name}\n{diff.get('summary', '')}{highlights}\n/runs/{run_id}",
        "monitor": monitor_name,
        "run_id": str(run_id),
        "diff": diff,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
        logger.info("monitor_alert_webhook_sent", run_id=str(run_id))
    except Exception as e:
        # Best-effort: a bad webhook must not fail the run's finalize.
        logger.warning("monitor_alert_webhook_failed", error=str(e))
