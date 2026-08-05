"""
Tests for the LangGraph supervisor's HITL pause points.

The pauses have to be the graph's own: compiled with a checkpointer and
interrupt_before, so `.invoke()` stops between stages instead of running
research -> analyse -> review -> write -> edit -> END in one call. run_service's
3-stage gate can re-invoke with hand-rolled state and believe it is stopping
after each stage while the graph never actually pauses.

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
        # Emit the reviewer's real routing contract (a leading VERDICT field), so
        # route_after_review parses it the way it parses live reviewer output.
        return {"review_output": f"VERDICT: {next(reviews)}", "retry_count": state.get("retry_count", 0) + 1}

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
    assert crew_module.review_verdict(out.get("review_output")) == "PASS"
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
    assert crew_module.review_verdict(out2.get("review_output")) == "PASS"
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


# Budget ceiling: the reviewer retry loop must stop once the run's accumulated
# LLM spend reaches RUN_COST_CEILING_USD, rather than burning the full retry
# allowance regardless of cost.

def _fail_state(**over):
    state = dict(BASE_STATE)
    state.update(review_output="VERDICT: FAIL", retry_count=0, spent_usd=0.0, token_usages=[])
    state.update(over)
    return state


def test_route_after_review_ships_partial_when_over_budget(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "RUN_COST_CEILING_USD", 1.0)
    # A FAIL that would normally retry, but prior spend already exceeds the ceiling.
    assert crew_module.route_after_review(_fail_state(spent_usd=2.0)) == "write"


def test_route_after_review_retries_within_budget(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "RUN_COST_CEILING_USD", 100.0)
    assert crew_module.route_after_review(_fail_state(spent_usd=0.0)) == "research"


def test_route_after_review_counts_in_flight_tokens_toward_budget(monkeypatch):
    from config import settings
    # 70B priced at (0.00059, 0.00079)/1k → 1k+1k ≈ $0.00138, over a $0.001 ceiling.
    monkeypatch.setattr(settings, "RUN_COST_CEILING_USD", 0.001)
    state = _fail_state(token_usages=[{
        "agent_name": "analyst", "model": "groq/llama-3.3-70b-versatile",
        "prompt_tokens": 1000, "completion_tokens": 1000,
    }])
    assert crew_module.route_after_review(state) == "write"


def test_route_after_review_ceiling_disabled_allows_retry(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "RUN_COST_CEILING_USD", None)
    # Even with huge spend, a None ceiling disables the budget guard (retry cap
    # of 3 still bounds the loop).
    assert crew_module.route_after_review(_fail_state(spent_usd=999.0)) == "research"


def test_route_after_review_retry_cap_still_bounds_loop(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "RUN_COST_CEILING_USD", None)
    # retry_count exhausted → ship regardless of budget being disabled.
    assert crew_module.route_after_review(_fail_state(retry_count=3)) == "write"


def test_lead_intel_contract_rejects_missing_buyer_freshness_and_readiness():
    failures = crew_module.lead_intel_contract_failures(
        "## Company Overview\nGeneric profile only.",
        "CISO",
    )
    assert any("Target Buyer" in failure for failure in failures)
    assert any("Purchase-Readiness" in failure for failure in failures)
    assert any("CISO" in failure for failure in failures)
    assert any("source URL" in failure for failure in failures)
    assert any("publication/update date" in failure for failure in failures)


def test_lead_intel_contract_accepts_sourced_target_buyer_report():
    output = """## Target Buyer — CISO
Verified person: Jane Doe, Chief Information Security Officer
Supporting source and date: https://example.com/leadership — 2026-06-01
## Purchase-Readiness Evidence
Dated security hiring and compliance initiative.
## Source Evidence Ledger
| CISO title | https://example.com/leadership | 2026-06-01 |
"""
    assert crew_module.lead_intel_contract_failures(output, "CISO", current_year=2026) == []


def test_lead_intel_contract_rejects_stale_executive_title():
    output = """## Target Buyer — CISO
Verified person: Former Security Leader
Supporting source and date: https://example.com/old-leadership — 2022-05-01
## Purchase-Readiness Evidence
Recent compliance investment.
## Source Evidence Ledger
| readiness | https://example.com/news | 2026-06-01 |
"""
    failures = crew_module.lead_intel_contract_failures(output, "CISO", current_year=2026)
    assert "Target-buyer title is supported only by stale sources" in failures


def test_failed_lead_review_retries_once_then_warns_at_end(monkeypatch):
    monkeypatch.setattr(crew_module.settings, "RUN_COST_CEILING_USD", None)
    state = _fail_state(retry_count=1)
    assert crew_module.route_after_lead_review(state) == "lead_intel"
    state["retry_count"] = 2
    assert crew_module.route_after_lead_review(state) == "end"


# Researcher retry-budget escalation: a re-run after a review FAIL gets a deeper
# budget than the deliberately-shallow first pass, so it acts on the feedback
# instead of re-failing the same undersized pass and re-billing it.

def test_researcher_budget_first_pass_uses_base(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "RESEARCHER_MAX_ITER", 2)
    monkeypatch.setattr(settings, "RESEARCHER_MAX_TOKENS", 900)
    monkeypatch.setattr(settings, "RESEARCHER_RETRY_TOKEN_STEP", 500)
    assert crew_module._researcher_budget(0) == (2, 900)


def test_researcher_budget_escalates_per_retry(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "RESEARCHER_MAX_ITER", 2)
    monkeypatch.setattr(settings, "RESEARCHER_MAX_TOKENS", 900)
    monkeypatch.setattr(settings, "RESEARCHER_RETRY_TOKEN_STEP", 500)
    assert crew_module._researcher_budget(1) == (3, 1400)
    assert crew_module._researcher_budget(2) == (4, 1900)


def test_researcher_budget_is_monotonic_and_never_below_base(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "RESEARCHER_MAX_ITER", 2)
    monkeypatch.setattr(settings, "RESEARCHER_MAX_TOKENS", 900)
    monkeypatch.setattr(settings, "RESEARCHER_RETRY_TOKEN_STEP", 500)
    # A negative/garbage retry_count clamps to the base pass, never smaller.
    assert crew_module._researcher_budget(-1) == (2, 900)
    prev = (0, 0)
    for rc in range(0, 4):
        cur = crew_module._researcher_budget(rc)
        assert cur >= prev
        prev = cur


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
