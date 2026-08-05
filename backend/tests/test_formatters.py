"""formatters/ must stay wired into routers/outputs.py via
formatters.format_output. Unreferenced, it goes dead without any test failing
and a format="linkedin" run downloads as raw Markdown instead of LinkedIn-safe
plain text."""
from formatters import format_output
from formatters.linkedin import format_linkedin
from formatters.report import format_report
from formatters.summary import format_summary


def test_format_linkedin_converts_headers_to_bold():
    text = "# Title\n\n## Subheading\n\nBody text."
    result = format_linkedin(text)
    assert "**Title**" in result
    assert "**Subheading**" in result
    assert "#" not in result


def test_format_linkedin_preserves_citation_urls():
    """The link-stripping regex must keep the URL, not just the link text —
    dropping it silently strips every source attribution from the post."""
    text = "Revenue grew 40% [TechCrunch](https://techcrunch.com/article1)."
    result = format_linkedin(text)
    assert "https://techcrunch.com/article1" in result
    assert "TechCrunch" in result
    assert "[" not in result and "]" not in result


def test_format_linkedin_converts_bullets():
    text = "- first point\n* second point"
    result = format_linkedin(text)
    assert "• first point" in result
    assert "• second point" in result


def test_format_linkedin_strips_code_ticks():
    text = "Use `format_output` to dispatch."
    result = format_linkedin(text)
    assert "`" not in result
    assert "format_output" in result


def test_format_report_prepends_header_when_missing():
    assert format_report("Just body text.").startswith("# Research Report")


def test_format_report_passthrough_when_header_present():
    text = "# Already titled\n\nBody."
    assert format_report(text) == text


def test_format_summary_is_passthrough():
    text = "Some summary text."
    assert format_summary(text) == text


def test_format_output_dispatches_by_format_string():
    assert format_output("linkedin", "# Title").strip() == "**Title**"
    assert format_output("report", "body").startswith("# Research Report")
    assert format_output("summary", "body") == "body"


def test_format_output_falls_back_to_report_for_unknown_format():
    result = format_output("nonsense", "body")
    assert result.startswith("# Research Report")
