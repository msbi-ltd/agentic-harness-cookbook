import json

import pytest

from scripts.ledger import MistakeRecord, append_record, report


def _rec(**kw):
    base = dict(
        occurred_at="2026-08-27T20:00:00+00:00",
        kind="unverified-claim",
        caught_by="user",
        summary="stated a fact I hadn't checked",
    )
    base.update(kw)
    return MistakeRecord(**base)


def test_append_and_read_back(tmp_path):
    path = tmp_path / "ledger.jsonl"
    append_record(_rec(), path=path)
    append_record(_rec(caught_by="tool"), path=path)
    lines = path.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["kind"] == "unverified-claim"


def test_report_tallies_caught_by(tmp_path):
    path = tmp_path / "ledger.jsonl"
    append_record(_rec(caught_by="user"), path=path)
    append_record(_rec(caught_by="user"), path=path)
    append_record(_rec(caught_by="tool"), path=path)
    assert report(path) == {"user": 2, "tool": 1}


def test_report_on_missing_ledger_is_empty(tmp_path):
    assert report(tmp_path / "nope.jsonl") == {}


def test_invalid_kind_is_refused(tmp_path):
    with pytest.raises(ValueError):
        append_record(_rec(kind="made-up-kind"), path=tmp_path / "l.jsonl")


def test_invalid_caught_by_is_refused(tmp_path):
    with pytest.raises(ValueError):
        append_record(_rec(caught_by="cosmic-rays"), path=tmp_path / "l.jsonl")


def test_blank_summary_is_refused(tmp_path):
    with pytest.raises(ValueError):
        append_record(_rec(summary="   "), path=tmp_path / "l.jsonl")


def test_corrected_defaults_to_none_not_false(tmp_path):
    # "not measured" must be distinguishable from "measured, not corrected".
    assert _rec().corrected is None


def _append_many(path_str):
    # Module-level so it's picklable by ProcessPoolExecutor.
    from pathlib import Path
    for _ in range(50):
        append_record(_rec(caught_by="tool"), path=Path(path_str))


def test_concurrent_appends_do_not_corrupt_lines(tmp_path):
    # Four processes appending under flock: every line must be valid JSON and
    # the total count exact, with no interleaved/torn lines.
    from concurrent.futures import ProcessPoolExecutor

    path = tmp_path / "ledger.jsonl"
    with ProcessPoolExecutor(max_workers=4) as ex:
        list(ex.map(_append_many, [str(path)] * 4))

    lines = path.read_text().splitlines()
    assert len(lines) == 200
    for ln in lines:
        json.loads(ln)  # raises if any line is torn
