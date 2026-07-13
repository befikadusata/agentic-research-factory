"""
Regression tests for §9.1: agents/crew.py's Langfuse integration used to call
lf.trace(name=...)/trace.span(name=...), an API that doesn't exist on the
pinned langfuse>=4.12.0 SDK (v4 replaced the old trace/span object model with
an OTEL-based start_as_current_observation() context manager). Dormant only
because get_langfuse() returns None until LANGFUSE_PUBLIC_KEY/SECRET_KEY are
set — the first person who sets them per .env.example's own instructions
would crash every run with AttributeError.

These tests instantiate a *real* Langfuse client (pointed at an unreachable
host, so no network access is required) rather than mocking get_langfuse(),
so a future rename/removal on the langfuse side fails the test instead of
silently rotting again.
"""
import pytest
from unittest.mock import MagicMock
from langfuse import Langfuse
import agents.crew as crew_module


class _FakeCrewOutput:
    def __init__(self, text, prompt_tokens=10, completion_tokens=5):
        self._text = text
        self.token_usage = MagicMock(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)

    def __str__(self):
        return self._text


@pytest.fixture
def real_langfuse_client(monkeypatch):
    lf = Langfuse(public_key="pk-test", secret_key="sk-test", host="http://localhost:1")
    monkeypatch.setattr(crew_module, "get_langfuse", lambda: lf)
    yield lf


def test_run_crew_node_succeeds_with_real_langfuse_client(monkeypatch, real_langfuse_client):
    fake_crew = MagicMock()
    fake_crew.kickoff.return_value = _FakeCrewOutput("RESULT")
    monkeypatch.setattr(crew_module, "Crew", MagicMock(return_value=fake_crew))

    result = crew_module._run_crew_node([], [], {}, {"configurable": {}}, "research_output", "researcher")

    assert result["research_output"] == "RESULT"
    assert result["token_usages"] == [{
        "agent_name": "research_output",
        # No litellm call fired under the mock, so the served model resolves to
        # the configured primary (see resolve_actual_model — H4).
        "model": crew_module.resolve_actual_model("researcher"),
        "prompt_tokens": 10,
        "completion_tokens": 5,
    }]


def test_run_crew_node_propagates_crew_failure_with_real_langfuse_client(monkeypatch, real_langfuse_client):
    fake_crew = MagicMock()
    fake_crew.kickoff.side_effect = RuntimeError("boom")
    monkeypatch.setattr(crew_module, "Crew", MagicMock(return_value=fake_crew))

    with pytest.raises(RuntimeError, match="boom"):
        crew_module._run_crew_node([], [], {}, {"configurable": {}}, "research_output", "researcher")


def test_run_crew_node_works_without_langfuse_configured(monkeypatch):
    """get_langfuse() returns None in the default (no env vars set) case —
    must still work with tracing fully skipped."""
    monkeypatch.setattr(crew_module, "get_langfuse", lambda: None)
    fake_crew = MagicMock()
    fake_crew.kickoff.return_value = _FakeCrewOutput("RESULT")
    monkeypatch.setattr(crew_module, "Crew", MagicMock(return_value=fake_crew))

    result = crew_module._run_crew_node([], [], {}, {"configurable": {}}, "research_output", "researcher")
    assert result["research_output"] == "RESULT"
