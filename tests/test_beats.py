import pytest

from scripts import beats


@pytest.fixture(autouse=True)
def _beats_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("BEATS_DIR", str(tmp_path))
    return tmp_path


def test_on_time_when_deadline_not_passed():
    beats.report("t1", due_in_seconds=600, doing="running the backend suite", now=1000.0)
    assert beats.check("t1", now=1100.0).startswith("on-time")


def test_overdue_when_deadline_passed():
    beats.report("t1", due_in_seconds=60, doing="running tests", now=1000.0)
    msg = beats.check("t1", now=2000.0)
    assert msg.startswith("overdue")
    assert "running tests" in msg


def test_done_expects_no_further_beat():
    beats.report("t1", due_in_seconds=60, doing="x", now=1000.0)
    beats.done("t1", now=1010.0)
    assert beats.check("t1", now=9999.0).startswith("done")


def test_unknown_task_never_recorded():
    assert beats.check("never-seen", now=1000.0).startswith("unknown")


def test_path_traversal_task_id_is_rejected():
    with pytest.raises(ValueError):
        beats.report("../../escape", 60, "x", now=1000.0)
    with pytest.raises(ValueError):
        beats.check("../../escape", now=1000.0)


def test_partial_write_does_not_crash_check(tmp_path):
    # Simulate a torn write: invalid JSON in the beat file.
    (tmp_path / "t1.json").write_text('{"task_id": "t1", "sta')
    assert beats.check("t1", now=1000.0).startswith("unknown")


def test_no_leftover_tmp_file_after_report(tmp_path):
    beats.report("t1", 60, "x", now=1000.0)
    assert [p.name for p in tmp_path.iterdir()] == ["t1.json"]


def test_long_step_extends_the_deadline_before_it_starts():
    beats.report("t1", due_in_seconds=60, doing="short step", now=1000.0)
    # re-report with a longer window BEFORE the long op
    beats.report("t1", due_in_seconds=900, doing="full suite ~13m", now=1050.0)
    assert beats.check("t1", now=1500.0).startswith("on-time")
