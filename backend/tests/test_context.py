"""Unit tests for utils.context.compact_text (gap #4): bound re-fed inter-agent
context without dropping tail-anchored info (citations, conclusions)."""
from utils.context import compact_text, _ELISION


def test_under_budget_is_unchanged():
    text = "short research brief"
    assert compact_text(text, 6000) == text


def test_empty_and_none_are_safe():
    assert compact_text("", 100) == ""
    assert compact_text(None, 100) == ""


def test_over_budget_keeps_head_and_tail():
    head_marker = "HEAD-START"
    tail_marker = "TAIL-END-CITATION"
    body = "x" * 5000
    text = head_marker + body + tail_marker
    out = compact_text(text, 1000)

    assert len(out) <= 1000
    assert out.startswith(head_marker)          # head survives
    assert out.endswith(tail_marker)            # tail survives (unlike text[:N])
    assert _ELISION in out                       # elision is explicit
    assert len(out) < len(text)


def test_blunt_head_clip_would_have_dropped_the_tail():
    # Regression intent: the old `text[:N]` clip loses the citations at the end.
    tail = "SOURCE: report.pdf (Page: 9)"
    text = ("a" * 4000) + tail
    assert tail not in text[:1000]               # what the old clip did
    assert tail in compact_text(text, 1000)      # what we do now


def test_tiny_budget_degrades_to_plain_clip():
    text = "y" * 500
    out = compact_text(text, len(_ELISION) - 1)
    assert out == text[: len(_ELISION) - 1]
