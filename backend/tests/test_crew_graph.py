"""
Regression tests for the LangGraph supervisor's HITL pause points.

Before this fix, `build_graph()` compiled the graph with no checkpointer and no
interrupt_before, so a single `.invoke()` ran research -> analyse -> review ->
write -> edit -> END in one call. run_service's 3-stage HITL gate re-invoked the
graph with hand-rolled state and believed it was stopping after each stage, but
the graph itself never actually paused.

These tests exercise the real compiled graph (routing + interrupt config) with
fast, deterministic fake node functions swapped in for the CrewAI-backed ones,
so the pause/resume behavior can be verified without real LLM calls.
"""
import agents.crew as crew_module

BASE_STATE = {
    "topic": "test topic",
    "vertical": None,
    "task_type": "research_report",
    "context_docs": "",
    "workspace_id": "",
    "collection_name": None,
    "output_format": "report",
    "plan_output": "",
    "research_output": "",
    "analysis_output": "",
    "final_output": "",
    "review_output": "",
    "retry_count": 0,
    "step_callback": None,
    "user_feedback": "",
    "token_usages": [],
}


def _build_fake_graph(monkeypatch, review_sequence):
    """Swap the CrewAI-backed node functions for cheap fakes, then rebuild the
    graph so it picks them up (build_graph() resolves node_* by name at call
    time), preserving the real routing/interrupt configuration under test."""
    reviews = iter(review_sequence)

    def fake_plan(state):
        return {"plan_output": "PLAN"}

    def fake_research(state):
        tag = "-retry" if "FAIL" in (state.get("review_output") or "") else ""
        return {"research_output": f"RESEARCH{tag}"}

    def fake_analyse(state):
        return {"analysis_output": "ANALYSIS"}

    def fake_review(state):
        return {"review_output": next(reviews), "retry_count": state.get("retry_count", 0) + 1}

    def fake_write(state):
        return {"final_output": "DRAFT"}

    def fake_edit(state):
        return {"final_output": state["final_output"] + "-EDITED"}

    monkeypatch.setattr(crew_module, "node_plan", fake_plan)
    monkeypatch.setattr(crew_module, "node_research", fake_research)
    monkeypatch.setattr(crew_module, "node_analyse", fake_analyse)
    monkeypatch.setattr(crew_module, "node_review", fake_review)
    monkeypatch.setattr(crew_module, "node_write", fake_write)
    monkeypatch.setattr(crew_module, "node_edit", fake_edit)

    return crew_module.build_graph()


def test_single_invoke_does_not_run_to_completion(monkeypatch):
    graph = _build_fake_graph(monkeypatch, ["PASS"])
    config = {"configurable": {"thread_id": "t-single-invoke"}}

    out = graph.invoke(dict(BASE_STATE), config)

    assert out.get("research_output") == "RESEARCH"
    assert out.get("analysis_output") == ""
    assert out.get("final_output") == ""
    assert graph.get_state(config).next == ("analyse",)

    graph.checkpointer.delete_thread("t-single-invoke")


def test_resume_after_research_runs_only_analysis_and_review(monkeypatch):
    graph = _build_fake_graph(monkeypatch, ["PASS"])
    config = {"configurable": {"thread_id": "t-resume-analysis"}}

    graph.invoke(dict(BASE_STATE), config)
    out = graph.invoke(None, config)

    assert out.get("analysis_output") == "ANALYSIS"
    assert out.get("review_output") == "PASS"
    assert out.get("final_output") == ""
    assert graph.get_state(config).next == ("write",)

    graph.checkpointer.delete_thread("t-resume-analysis")


def test_failed_review_retries_research_and_pauses_again(monkeypatch):
    """A FAIL review re-runs research transparently, but must pause again before
    re-running analysis rather than silently redoing already-approved work."""
    graph = _build_fake_graph(monkeypatch, ["FAIL", "PASS"])
    config = {"configurable": {"thread_id": "t-retry"}}

    graph.invoke(dict(BASE_STATE), config)
    out = graph.invoke(None, config)  # analyse -> review(FAIL) -> research(retry)

    assert out.get("research_output") == "RESEARCH-retry"
    assert out.get("final_output") == ""
    assert graph.get_state(config).next == ("analyse",)

    out2 = graph.invoke(None, config)  # analyse -> review(PASS)
    assert out2.get("review_output") == "PASS"
    assert graph.get_state(config).next == ("write",)

    graph.checkpointer.delete_thread("t-retry")


def test_full_resume_sequence_reaches_end(monkeypatch):
    graph = _build_fake_graph(monkeypatch, ["PASS"])
    config = {"configurable": {"thread_id": "t-full"}}

    graph.invoke(dict(BASE_STATE), config)  # -> pause before analyse
    graph.invoke(None, config)              # -> pause before write
    out = graph.invoke(None, config)        # -> write, edit, END

    assert out.get("final_output") == "DRAFT-EDITED"
    assert graph.get_state(config).next == ()

    graph.checkpointer.delete_thread("t-full")


def test_resume_from_marker_reenters_at_analyse_in_fresh_thread(monkeypatch):
    """Cross-process durable resume: run_service rebuilds state from the DB in a
    brand-new thread (the in-memory checkpoint is gone) and sets `_resume_from`.
    interrupt_before must still fire, so the first invoke pauses *before* analyse
    and invoke(None) runs analyse -> review -> pause before write — without
    re-running plan/research."""
    graph = _build_fake_graph(monkeypatch, ["PASS"])
    config = {"configurable": {"thread_id": "t-resume-marker"}}

    state = dict(BASE_STATE)
    state["research_output"] = "RESEARCH"          # rebuilt from the Run row
    state["_resume_from"] = "analyse"

    out = graph.invoke(state, config)              # loads state, pauses before analyse
    assert graph.get_state(config).next == ("analyse",)
    assert out.get("analysis_output") == ""        # analyse has NOT run yet

    out = graph.invoke(None, config)               # analyse -> review(PASS) -> pause before write
    assert out.get("analysis_output") == "ANALYSIS"
    assert graph.get_state(config).next == ("write",)

    graph.checkpointer.delete_thread("t-resume-marker")


def test_resume_from_marker_reenters_at_write_in_fresh_thread(monkeypatch):
    """Same durable-resume path for the write segment: re-enter at `write` with
    analysis rebuilt from the DB, run write -> edit -> END."""
    graph = _build_fake_graph(monkeypatch, ["PASS"])
    config = {"configurable": {"thread_id": "t-resume-write"}}

    state = dict(BASE_STATE)
    state["research_output"] = "RESEARCH"
    state["analysis_output"] = "ANALYSIS"
    state["_resume_from"] = "write"

    graph.invoke(state, config)                    # pauses before write
    assert graph.get_state(config).next == ("write",)

    out = graph.invoke(None, config)               # write -> edit -> END
    assert out.get("final_output") == "DRAFT-EDITED"
    assert graph.get_state(config).next == ()

    graph.checkpointer.delete_thread("t-resume-write")
