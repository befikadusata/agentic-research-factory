from formatters.linkedin import format_linkedin
from formatters.report import format_report
from formatters.summary import format_summary

_FORMATTERS = {
    "linkedin": format_linkedin,
    "report": format_report,
    "summary": format_summary,
}


def format_output(fmt: str, raw_markdown: str) -> str:
    """Apply the format-specific post-processor for a run's `format` field.

    Falls back to `format_report` (a no-op passthrough for already-Markdown
    content) for any unrecognized format string, rather than raising.
    """
    formatter = _FORMATTERS.get(fmt, format_report)
    return formatter(raw_markdown)
