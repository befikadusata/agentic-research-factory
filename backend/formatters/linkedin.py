import re

def format_linkedin(raw_markdown: str) -> str:
    """Convert markdown to LinkedIn-friendly plain text (bold via ** only)."""
    text = raw_markdown
    text = re.sub(r'^#{1,3} (.+)$', r'**\1**', text, flags=re.MULTILINE)
    text = re.sub(r'^#{4,6} ', '', text, flags=re.MULTILINE)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'^\s*[-*] ', '• ', text, flags=re.MULTILINE)
    return text.strip()
