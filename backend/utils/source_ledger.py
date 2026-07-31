"""Record the URLs a run actually retrieved, so citations can be checked against them.

An agent can invent a citation that looks perfectly ordinary — a live run cited
`dataqualityreport.com` and `enterprise-search.com`, neither of which it ever
visited. Nothing in the URL string gives that away; the only thing that
distinguishes a real citation from a fabricated one is whether the run actually
fetched the page. Published work on deep-research agents converges on the same
answer (arXiv 2605.06635, arXiv 2605.27700): ground each reference against what
retrieval really returned, and *label* the result rather than deleting it,
because a filter that silently drops citations trades one invisible failure for
another.

Only sources that came back from an external system are recorded — search-engine
results and successful scrapes. A URL the model merely *asked* to scrape is not
evidence of anything, and recording that would launder a hallucination into a
verified citation.

Process-global and reset per segment, which is sound under the pipeline's Celery
`--concurrency=1` (one run executes at a time — the same invariant
`utils.cost_tracker._side_costs` and `resolve_actual_model` already rely on).
The reset is not optional: a Celery worker process is reused across tasks, so
without it one run would inherit the previous run's sources and verify against
them.
"""

from urllib.parse import parse_qsl, urlencode, urlsplit

from logger import logger

# Parameters that identify a visitor or campaign rather than a document, so two
# URLs differing only by these are the same source. Deliberately conservative:
# `ref` is excluded because sites like GitHub give it meaning, and over-eager
# normalisation would let a fabricated URL match a real one.
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_name", "gclid", "gbraid", "wbraid", "fbclid", "msclkid",
    "mc_cid", "mc_eid", "igshid", "vero_id", "_hsenc", "_hsmi", "yclid",
}

# A run cites a handful of sources but can search many times; cap the ledger so
# a pathological run can't grow the metrics JSON without bound.
_MAX_SOURCES = 500

_seen_sources: set[str] = set()


def canonical_url(url: str) -> str:
    """Reduce a URL to a comparison key, per RFC 3986 syntax-based normalisation.

    Scheme is dropped rather than lowercased, so http and https forms of the
    same page match; likewise a leading `www.`, a default port, a trailing
    slash, the fragment, and tracking parameters. Remaining query parameters are
    kept and sorted, since they routinely select the actual document.
    """
    raw = (url or "").strip()
    try:
        parts = urlsplit(raw)
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:
        # Malformed authority (bad port, unbalanced brackets). Nothing to
        # normalise — fall back to the raw string so it can still match itself.
        return raw.lower()

    if host.startswith("www."):
        host = host[4:]
    suffix = "" if port in (None, 80, 443) else f":{port}"

    path = (parts.path or "").rstrip("/")
    kept = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    query = f"?{urlencode(sorted(kept))}" if kept else ""

    return f"{host}{suffix}{path}{query}"


def reset_seen_sources(previous: list[str] | None = None) -> None:
    """Start a segment's ledger, optionally seeded with earlier segments' sources.

    Runs execute as separate Celery tasks in fresh processes, so the research
    segment's sources have to be carried forward for the write segment — which
    is where the final report's citations are extracted — to verify against them.
    """
    _seen_sources.clear()
    for url in previous or []:
        _seen_sources.add(canonical_url(url))


def record_retrieved_url(url: str) -> None:
    """Note a URL an external system actually returned. Never raises: this is
    bookkeeping, and it must not be able to break the tool call it observes."""
    try:
        if not url or len(_seen_sources) >= _MAX_SOURCES:
            return
        key = canonical_url(url)
        if key:
            _seen_sources.add(key)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("source_ledger_record_failed", error=str(e))


def take_seen_sources() -> list[str]:
    """The canonical sources retrieved so far, sorted for a stable stored value."""
    return sorted(_seen_sources)
