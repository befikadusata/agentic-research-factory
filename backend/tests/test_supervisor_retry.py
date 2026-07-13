"""
Regression test for M1: the whole-graph tenacity retry used to re-invoke the
supervisor with the *original* input state on every attempt. LangGraph
checkpoints after each super-step, so when a mid-graph node fails the earlier
nodes' output is already checkpointed — but replaying the original input
restarts from START and overwrites those channels with the stale entry values
(e.g. plan_output -> ""), discarding completed work and re-billing it.

_invoke_supervisor_with_retry now carries the input only on the first attempt
and resumes from the checkpoint (input=None) on retries, so only the failed
super-step re-runs.
"""
import pytest
from tenacity import RetryError, wait_none
import services.run_service as run_service


@pytest.fixture(autouse=True)
def _no_backoff_wait(monkeypatch):
    # Keep the retry immediate so the test doesn't sleep on the real backoff.
    monkeypatch.setattr(run_service, "wait_exponential", lambda **kw: wait_none())


class _FlakySupervisor:
    """Fails its first invoke, succeeds on the next; records each input."""

    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.inputs = []

    def invoke(self, state, config):
        self.inputs.append(state)
        if len(self.inputs) <= self.fail_times:
            raise RuntimeError("transient node failure")
        return {"ok": True}


@pytest.mark.asyncio
async def test_retry_resumes_from_checkpoint_instead_of_replaying_input():
    sup = _FlakySupervisor(fail_times=1)
    entry = {"plan_output": "PLAN", "_resume_from": "analyse"}

    result = await run_service._invoke_supervisor_with_retry(
        sup, entry, {"configurable": {"thread_id": "t-retry"}}
    )

    assert result == {"ok": True}
    # First attempt carries the reconstructed state...
    assert sup.inputs[0] == entry
    # ...but the retry resumes from the checkpoint, NOT the stale input, so the
    # checkpointed plan_output can't be clobbered back to "".
    assert sup.inputs[1] is None


@pytest.mark.asyncio
async def test_first_attempt_success_passes_input_through():
    sup = _FlakySupervisor(fail_times=0)
    entry = {"plan_output": "PLAN"}

    result = await run_service._invoke_supervisor_with_retry(
        sup, entry, {"configurable": {"thread_id": "t-ok"}}
    )

    assert result == {"ok": True}
    assert sup.inputs == [entry]  # no retry, input used exactly once


@pytest.mark.asyncio
async def test_retry_exhaustion_raises():
    sup = _FlakySupervisor(fail_times=99)  # always fails

    # tenacity wraps the final failure in RetryError (execute_run already unwraps
    # the embedded Future — run_service handles the RetryError contract).
    with pytest.raises(RetryError):
        await run_service._invoke_supervisor_with_retry(
            sup, {"plan_output": "PLAN"}, {"configurable": {"thread_id": "t-fail"}}
        )

    # stop_after_attempt(3): one initial + two retries.
    assert len(sup.inputs) == 3
    assert sup.inputs[0] == {"plan_output": "PLAN"}
    assert sup.inputs[1] is None
    assert sup.inputs[2] is None
