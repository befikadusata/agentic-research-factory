"""
Regression tests for ReAct scaffolding leaking into the user-facing deliverable.

A live Groq-backed run persisted "Thought: I now can give a great answer\n\n"
ahead of the report body in runs.final_output. CrewAI only strips that preamble
when the model also emits the literal "Final Answer:" marker it splits on; when
the marker is missing the raw text is surfaced, and nothing downstream removed
it before it reached the user.
"""
import agents.crew as crew_module
from utils.agent_output import strip_agent_scaffolding

REPORT = "# Impact of Open-Weight LLMs\n## Situation\nThe emergence of..."


def test_strips_the_leaked_thought_preamble():
    """The exact string observed in the wild."""
    assert strip_agent_scaffolding(
        f"Thought: I now can give a great answer\n\n{REPORT}"
    ) == REPORT


def test_strips_thought_plus_final_answer_marker():
    assert strip_agent_scaffolding(
        f"Thought: I now know the final answer\nFinal Answer: {REPORT}"
    ) == REPORT


def test_strips_bare_template_sentence_without_thought_prefix():
    assert strip_agent_scaffolding(f"I now can give a great answer\n\n{REPORT}") == REPORT


def test_strips_final_answer_rendered_as_markdown_heading():
    assert strip_agent_scaffolding(f"## Final Answer:\n{REPORT}") == REPORT


def test_leaves_clean_output_untouched():
    assert strip_agent_scaffolding(REPORT) == REPORT


def test_keeps_body_that_merely_mentions_the_markers():
    """Only a *leading* block is scaffolding — the same words inside a report are
    content, and a report about agent frameworks may legitimately contain them."""
    body = (
        "# How ReAct agents work\n\n"
        "The agent emits `Thought:` on each step and closes with Final Answer:"
        " the completed response.\n"
    )
    assert strip_agent_scaffolding(body) == body.strip()


def test_does_not_reach_past_a_few_lines_into_a_derailed_output():
    """Many Thought/Action cycles is a different failure; deleting them all would
    disguise it. Past the cap the remaining text is left alone."""
    derailed = "\n".join(f"Thought: step {i}" for i in range(12)) + f"\n{REPORT}"
    cleaned = strip_agent_scaffolding(derailed)
    assert cleaned.startswith("Thought: step 4")
    assert REPORT in cleaned


def test_all_scaffolding_returns_the_original_rather_than_nothing():
    """An empty deliverable is worse than one with a stray preamble."""
    only_scaffolding = "Thought: I now can give a great answer\n"
    assert strip_agent_scaffolding(only_scaffolding) == only_scaffolding.strip()


def test_handles_empty_and_none():
    assert strip_agent_scaffolding("") == ""
    assert strip_agent_scaffolding(None) == ""


def test_crew_node_strips_before_the_output_reaches_state(monkeypatch):
    """The strip must happen at the node boundary, so every downstream consumer
    (reviewer, evaluator, citation extractor) sees the cleaned text — not just
    the DB column."""
    class FakeUsage:
        prompt_tokens = 10
        completion_tokens = 20

    class FakeResult:
        token_usage = FakeUsage()

        def __str__(self):
            return f"Thought: I now can give a great answer\n\n{REPORT}"

    class FakeCrew:
        def __init__(self, **kwargs):
            pass

        def kickoff(self):
            return FakeResult()

    monkeypatch.setattr(crew_module, "Crew", FakeCrew)
    monkeypatch.setattr(crew_module, "get_langfuse", lambda: None)
    monkeypatch.setattr(crew_module, "resolve_actual_model", lambda agent_key: "fake-model")
    monkeypatch.setattr(crew_module, "reset_actual_model", lambda: None)
    monkeypatch.setattr(crew_module, "reset_side_costs", lambda: None)
    monkeypatch.setattr(crew_module, "take_side_costs", lambda: [])

    result = crew_module._run_crew_node(
        [], [], {}, {"configurable": {"thread_id": "t-strip"}}, "final_output", "writer"
    )

    assert result["final_output"] == REPORT
    # Token accounting must survive the change.
    assert result["token_usages"][0]["prompt_tokens"] == 10
    assert result["token_usages"][0]["completion_tokens"] == 20
