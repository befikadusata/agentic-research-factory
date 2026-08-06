"""Robust JSON extraction from LLM responses.

LLM "return only JSON" output is unreliable in practice: models wrap it in
```json code fences, add a prose preamble ("Here is the JSON:"), or append a
trailing note. This centralizes a best-effort parse so every judge/rewriter
shares the same tolerant behavior.
"""
import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def parse_json(raw: str):
    """Parse a JSON value out of a (possibly messy) LLM response.

    Tries, in order: a straight parse, the contents of the first code fence, and
    the substring from the earliest opening bracket to its matching last close
    bracket. Raises json.JSONDecodeError if nothing parses — callers keep their
    existing try/except fallback, so a garbled response degrades gracefully
    rather than raising a surprise error type.
    """
    text = (raw or "").strip()

    # 1. straight parse — the happy path when the model actually obeyed.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. contents of the first ```/```json fence.
    fence = _FENCE_RE.search(text)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. earliest opening bracket → matching last close bracket of that kind,
    #    which strips a prose preamble/suffix around a bare object or array.
    candidates = []
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        if start != -1:
            candidates.append((start, open_ch, close_ch))
    for start, _open_ch, close_ch in sorted(candidates):
        end = text.rfind(close_ch)
        if end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue

    # Nothing parsed — re-raise the canonical error for the caller's fallback.
    return json.loads(text)
