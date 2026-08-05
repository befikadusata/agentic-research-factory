"""Bounding inter-agent context without an LLM call.

Every pipeline stage is already completion-capped (agents/*.py `max_tokens`), so
the output one stage feeds the next is inherently bounded — an inter-hop LLM
*summarization* pass would spend more tokens (its own prompt + completion) than
the prompt-token trim it buys, and on the free tier it adds a call to the same
rolling rate-limit window. So when a piece of re-fed context does exceed budget
we trim it structurally instead: keep a large head PLUS a tail slice, rather than
the blunt `text[:N]` head-only clip. The tail is where research output carries
its citations and analysis carries its conclusions — exactly the parts a
downstream reviewer/writer is penalized for missing.
"""

_ELISION = "\n\n…[content trimmed to fit context budget]…\n\n"


def compact_text(text: str | None, max_chars: int) -> str:
    """Return `text` bounded to at most ~`max_chars`, preserving both ends.

    Under budget (the common case, since stages are completion-capped) the text
    is returned unchanged. Over budget, a ~2/3 head and ~1/3 tail are kept, joined
    by an explicit elision marker, so tail-anchored information survives a clip.
    """
    if not text:
        return text or ""
    if len(text) <= max_chars:
        return text
    if max_chars <= len(_ELISION):
        return text[:max_chars]
    budget = max_chars - len(_ELISION)
    head = (budget * 2) // 3
    tail = budget - head
    return text[:head] + _ELISION + (text[-tail:] if tail else "")
