"""Strip ReAct scaffolding that leaks out of a CrewAI agent's final answer.

CrewAI's parser splits on the literal "Final Answer:" marker and keeps only what
follows (crewai/agents/parser.py), so a well-formed response arrives clean. When
a model reproduces the prompt template's "Thought:" preamble but omits the
marker, that split never happens and the raw text is surfaced instead — landing
verbatim in the user-facing deliverable. A live run persisted exactly that to
runs.final_output:

    Thought: I now can give a great answer

    # Impact of Open-Weight LLMs on Enterprise RAG Adoption in 2026
    ...

Only a *leading* scaffolding block is removed, and only a few lines of it. The
preamble sits at the very top when it leaks; an output carrying several
Thought/Action/Observation cycles is a different failure, and salvaging that by
deleting lines would disguise it rather than fix it.
"""

import re

# "Thought: ..." — one line of the ReAct preamble.
_THOUGHT_LINE = re.compile(r"[ \t]*Thought[ \t]*:[^\n]*(?:\n|\Z)")
# The template sentence on its own, for models that drop the "Thought:" prefix.
_TEMPLATE_LINE = re.compile(
    r"[ \t]*I now (?:can give a great answer|know the final answer)[.!]?[ \t]*(?:\n|\Z)",
    re.IGNORECASE,
)
# The marker CrewAI itself splits on; the console formatter renders it as a
# markdown heading, so accept that spelling too.
_FINAL_ANSWER = re.compile(r"[ \t]*#{0,6}[ \t]*Final Answer[ \t]*:[ \t]*")

# Enough for the observed leak (a Thought line, optionally a Final Answer
# marker) without reaching into content on a badly derailed output.
_MAX_SCAFFOLD_LINES = 4


def strip_agent_scaffolding(text: str | None) -> str:
    """Return `text` without a leading ReAct preamble.

    Text that carries no scaffolding comes back unchanged apart from surrounding
    whitespace. If stripping would consume everything, the original is kept —
    an empty deliverable is worse than one with a stray "Thought:" line.
    """
    if not text:
        return text or ""

    remainder = text.lstrip()
    for _ in range(_MAX_SCAFFOLD_LINES):
        marker = _FINAL_ANSWER.match(remainder)
        if marker:
            # Everything after the marker is the answer proper — the same rule
            # CrewAI's own parser applies.
            remainder = remainder[marker.end():]
            break
        line = _THOUGHT_LINE.match(remainder) or _TEMPLATE_LINE.match(remainder)
        if not line:
            break
        remainder = remainder[line.end():].lstrip()

    cleaned = remainder.strip()
    return cleaned if cleaned else text.strip()
