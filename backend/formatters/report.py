def format_report(raw_markdown: str) -> str:
    if not raw_markdown.startswith("#"):
        raw_markdown = f"# Research Report\n\n{raw_markdown}"
    return raw_markdown
