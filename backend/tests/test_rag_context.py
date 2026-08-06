"""Tests for neighbour expansion — `tools.rag.expand_context` and its parts.

No models and no database: the neighbour lookup is the one piece that touches
Postgres and it is patched out, so everything here is the logic that decides
*which* chunks belong together and how they are joined back up. That logic is
where the damage would be — a wrong page boundary produces a citation pointing at
the wrong page, and a wrong stitch silently deletes or duplicates document text.
"""
from unittest.mock import patch

from tools.rag import (
    _MAX_CONTEXT_CHUNKS,
    Candidate,
    _blocks_from,
    _Piece,
    _stitch,
    expand_context,
)


def _chunk(text, *, source="doc.pdf", page=1, ordinal=None, **extra):
    metadata = {"text": text, "source": source, "page": page, **extra}
    if ordinal is not None:
        metadata["ordinal"] = ordinal
    return metadata


def _candidate(text, **kwargs):
    return Candidate(chunk_id=text[:8], metadata=_chunk(text, **kwargs), score=1.0)


def _expand(candidates, found=None, radius=1):
    """Run expansion with the database replaced by a fixed lookup table."""
    with patch("tools.rag._get_client"), \
         patch("tools.rag._fetch_neighbours", return_value=found or {}):
        return expand_context(candidates, "ws_test", radius=radius)


def test_stitch_removes_the_overlap_the_splitter_added():
    left = "The rate limit is 600 requests per minute per workspace."
    right = "per minute per workspace. Enterprise tiers may request more."

    assert _stitch(left, right) == (
        "The rate limit is 600 requests per minute per workspace. "
        "Enterprise tiers may request more."
    )


def test_stitch_joins_with_a_break_when_there_is_no_overlap():
    assert _stitch("First part.", "Second part.") == "First part.\n\nSecond part."


def test_stitch_ignores_a_coincidental_short_tail():
    """Two unrelated chunks routinely share a few trailing characters — a space,
    a full stop, a common word. Splicing on that would delete real text."""
    left = "Backups are replicated within the selected region."
    right = "n. Recovery time objective is four hours."

    assert _stitch(left, right) == left + "\n\n" + right


def test_stitch_never_loses_the_tail_of_the_second_chunk():
    left = "a" * 500
    right = "a" * 400 + "UNIQUE TAIL"

    assert _stitch(left, right).endswith("UNIQUE TAIL")


def test_stitch_handles_an_empty_chunk():
    assert _stitch("", "text") == "\n\ntext"
    assert _stitch("text", "") == "text\n\n"


def test_stitching_reverses_the_real_splitter():
    """The one that matters: `_stitch` is measured against overlap the configured
    RecursiveCharacterTextSplitter actually produced, not against hand-written
    examples. The splitter cuts at separators, so the real overlap is rarely the
    configured 200 — assuming it would leave a seam of duplicated or missing text
    in every expanded passage.

    This is also the case neighbour expansion exists for: the fact and the
    sentence qualifying it end up in different chunks, and only the chunk holding
    the fact scores well enough to be retrieved.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    passage = " ".join(
        f"Rate limits are enforced per workspace and sentence {i} explains a "
        f"further consequence of that policy in some detail."
        for i in range(40)
    )
    parts = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200
    ).split_text(passage)
    assert len(parts) > 2, "test needs a passage the splitter actually divides"

    rejoined = parts[0]
    for part in parts[1:]:
        rejoined = _stitch(rejoined, part)

    assert rejoined == passage


def _piece(ordinal, *, page=1, source="doc.pdf", rank=None, text=None):
    return _Piece(
        source=source,
        page=page,
        ordinal=ordinal,
        metadata=_chunk(text or f"chunk {ordinal}.", source=source, page=page, ordinal=ordinal),
        rank=rank,
    )


def test_adjacent_pieces_become_one_block():
    blocks = _blocks_from([_piece(4, rank=0), _piece(5)])

    assert len(blocks) == 1
    assert [c["ordinal"] for c in blocks[0].chunks] == [4, 5]


def test_a_gap_in_ordinal_breaks_the_run():
    blocks = _blocks_from([_piece(1, rank=0), _piece(2), _piece(7, rank=1)])

    assert [[c["ordinal"] for c in b.chunks] for b in blocks] == [[1, 2], [7]]


def test_a_page_change_breaks_the_run_even_when_ordinals_are_adjacent():
    """The page number is the citation. A block spanning two pages could only be
    labelled with one of them, which is a citation pointing at the wrong page."""
    blocks = _blocks_from([_piece(3, page=2, rank=0), _piece(4, page=3)])

    assert len(blocks) == 2
    assert {b.page for b in blocks} == {2, 3}


def test_different_documents_never_merge():
    blocks = _blocks_from([_piece(1, source="a.pdf", rank=0), _piece(2, source="b.pdf", rank=1)])

    assert len(blocks) == 2


def test_blocks_are_ordered_by_the_best_result_they_contain():
    """Reading order within a block, relevance order between them — the agent
    reads the tool output top down and the strongest match should be first."""
    blocks = _blocks_from([_piece(9, rank=2), _piece(1, rank=0), _piece(5, rank=1)])

    assert [b.chunks[0]["ordinal"] for b in blocks] == [1, 5, 9]


def test_pieces_within_a_block_are_in_reading_order_not_rank_order():
    blocks = _blocks_from([_piece(6, rank=0), _piece(5, rank=1), _piece(4, rank=2)])

    assert [c["ordinal"] for c in blocks[0].chunks] == [4, 5, 6]


def test_chunks_without_an_ordinal_stay_separate():
    """Ingested before ordinals existed, and nothing backfills them. Position 0
    would be the wrong guess: every such chunk would become a neighbour of every
    other one in the same document."""
    blocks = _blocks_from([_piece(None, rank=0), _piece(None, rank=1)])

    assert len(blocks) == 2


def test_expansion_requests_the_chunks_either_side():
    with patch("tools.rag._get_client"), \
         patch("tools.rag._fetch_neighbours", return_value={}) as fetch:
        expand_context([_candidate("hit", ordinal=5)], "ws_test", radius=1)

    assert sorted(fetch.call_args[0][2]) == [("doc.pdf", 4), ("doc.pdf", 6)]


def test_expansion_does_not_request_negative_ordinals():
    with patch("tools.rag._get_client"), \
         patch("tools.rag._fetch_neighbours", return_value={}) as fetch:
        expand_context([_candidate("first chunk", ordinal=0)], "ws_test", radius=2)

    assert all(ordinal >= 0 for _, ordinal in fetch.call_args[0][2])


def test_expansion_does_not_request_chunks_already_retrieved():
    with patch("tools.rag._get_client"), \
         patch("tools.rag._fetch_neighbours", return_value={}) as fetch:
        expand_context(
            [_candidate("a", ordinal=4), _candidate("b", ordinal=5)], "ws_test", radius=1
        )

    assert sorted(fetch.call_args[0][2]) == [("doc.pdf", 3), ("doc.pdf", 6)]


def test_a_neighbour_is_stitched_onto_the_result():
    found = {("doc.pdf", 3): _chunk("Preceding sentence.", ordinal=3)}
    blocks = _expand([_candidate("The answer.", ordinal=4)], found)

    assert len(blocks) == 1
    assert blocks[0].text == "Preceding sentence.\n\nThe answer."


def test_a_neighbour_on_another_page_is_dropped():
    found = {("doc.pdf", 3): _chunk("Previous page tail.", page=1, ordinal=3)}
    blocks = _expand([_candidate("The answer.", page=2, ordinal=4)], found)

    assert len(blocks) == 1
    assert len(blocks[0].chunks) == 1
    assert blocks[0].text == "The answer."


def test_radius_zero_returns_the_results_unexpanded():
    with patch("tools.rag._get_client"), \
         patch("tools.rag._fetch_neighbours") as fetch:
        blocks = expand_context([_candidate("hit", ordinal=4)], "ws_test", radius=0)

    fetch.assert_not_called()
    assert len(blocks) == 1
    assert blocks[0].text == "hit"


def test_radius_zero_still_merges_results_that_are_adjacent():
    """Two neighbouring chunks both making the top 5 is exactly the case where
    concatenating them repeats the overlap. Merging is not part of expansion."""
    with patch("tools.rag._get_client"), patch("tools.rag._fetch_neighbours"):
        blocks = expand_context(
            [_candidate("Half a sentence", ordinal=4), _candidate("continues here.", ordinal=5)],
            "ws_test",
            radius=0,
        )

    assert len(blocks) == 1
    assert blocks[0].text == "Half a sentence\n\ncontinues here."


def test_results_without_ordinals_are_returned_unchanged():
    blocks = _expand([_candidate("legacy chunk")])

    assert len(blocks) == 1
    assert blocks[0].text == "legacy chunk"


def test_a_failed_neighbour_lookup_still_returns_the_results():
    """Expansion is an enhancement. Losing it must not lose the answer."""
    with patch("tools.rag._get_client"), \
         patch("tools.rag._fetch_neighbours", side_effect=RuntimeError("db gone")):
        blocks = expand_context([_candidate("the answer", ordinal=4)], "ws_test", radius=1)

    assert [b.text for b in blocks] == ["the answer"]


def test_expansion_is_budgeted_and_never_drops_a_result():
    candidates = [
        _candidate(f"hit {i}", ordinal=i * 10, page=i) for i in range(1, 6)
    ]
    with patch("tools.rag._get_client"), \
         patch("tools.rag._fetch_neighbours", return_value={}) as fetch:
        blocks = expand_context(candidates, "ws_test", radius=2)

    requested = len(fetch.call_args[0][2])
    assert len(candidates) + requested <= _MAX_CONTEXT_CHUNKS
    # The cap bites (radius 2 over 5 results wants 20 neighbours) and the results
    # themselves survive it.
    assert requested < 20
    assert len(blocks) == len(candidates)


def test_the_best_result_is_widened_first_when_the_budget_binds():
    candidates = [_candidate(f"hit {i}", ordinal=i * 10, page=i) for i in range(1, 6)]
    with patch("tools.rag._get_client"), \
         patch("tools.rag._fetch_neighbours", return_value={}) as fetch:
        expand_context(candidates, "ws_test", radius=2)

    requested = fetch.call_args[0][2]
    assert ("doc.pdf", 9) in requested and ("doc.pdf", 11) in requested


def test_empty_candidates_short_circuit():
    with patch("tools.rag._get_client") as client:
        assert expand_context([], "ws_test") == []
    client.assert_not_called()


def test_an_unsafe_collection_name_never_reaches_the_query():
    """The name is interpolated into SQL (identifiers cannot be bound), so the
    validation has to happen before the lookup, not inside it. Callers reach here
    via `retrieve`, which already validated — so this degrades to unexpanded
    results rather than raising."""
    with patch("tools.rag._get_client"), \
         patch("tools.rag._fetch_neighbours", return_value={}) as fetch:
        blocks = expand_context(
            [_candidate("hit", ordinal=1)], 'ws"; DROP TABLE x; --', radius=1
        )

    fetch.assert_not_called()
    assert [b.text for b in blocks] == ["hit"]
