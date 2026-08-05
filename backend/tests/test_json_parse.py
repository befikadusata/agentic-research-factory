"""Tests for the tolerant LLM-JSON parser.

Hand-stripping a single ``` fence then json.loads()'ing breaks on prose
preambles, ```json variants, and trailing notes — all of which models emit.
"""
import json
import pytest
from utils.json_parse import parse_json


def test_plain_object():
    assert parse_json('{"a": 1, "b": 2}') == {"a": 1, "b": 2}


def test_plain_array():
    assert parse_json('["x", "y", "z"]') == ["x", "y", "z"]


def test_json_code_fence():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_bare_code_fence():
    assert parse_json('```\n{"a": 1}\n```') == {"a": 1}


def test_prose_preamble_and_suffix_around_object():
    raw = 'Here is the JSON you asked for:\n{"changed": true, "summary": "s"}\nHope that helps!'
    assert parse_json(raw) == {"changed": True, "summary": "s"}


def test_prose_around_array():
    raw = 'Sure! The sub-queries are: ["one", "two"] — let me know.'
    assert parse_json(raw) == ["one", "two"]


def test_object_preferred_when_it_appears_first():
    # Earliest opening bracket wins: the object, not the inner array.
    raw = '{"items": ["a", "b"]}'
    assert parse_json(raw) == {"items": ["a", "b"]}


def test_unparseable_raises_json_error():
    # Callers rely on a JSONDecodeError to trigger their fallback path.
    with pytest.raises(json.JSONDecodeError):
        parse_json("not json at all, no brackets here")


def test_empty_raises():
    with pytest.raises(json.JSONDecodeError):
        parse_json("")
