import subprocess

from scripts import check_records
from scripts.check_records import evaluate, local_claims


def test_local_claims_reads_numbered_files(tmp_path):
    (tmp_path / "0001-first.md").write_text("x")
    (tmp_path / "0002-second.md").write_text("x")
    (tmp_path / "notes.md").write_text("x")  # unnumbered, ignored
    claims = local_claims(str(tmp_path))
    assert sorted(c.number for c in claims) == ["0001", "0002"]


def test_no_collision_passes(tmp_path, monkeypatch):
    (tmp_path / "0001-a.md").write_text("x")
    (tmp_path / "0002-b.md").write_text("x")
    monkeypatch.setattr(check_records, "remote_claims", lambda branches, d: [])
    assert evaluate(str(tmp_path), []) == 0


def test_two_local_files_same_number_is_a_collision(tmp_path, monkeypatch):
    (tmp_path / "0007-a.md").write_text("x")
    (tmp_path / "0007-b.md").write_text("x")
    monkeypatch.setattr(check_records, "remote_claims", lambda branches, d: [])
    assert evaluate(str(tmp_path), []) == 1


def test_local_vs_remote_collision(tmp_path, monkeypatch):
    (tmp_path / "0009-a.md").write_text("x")
    remote = [check_records.Claim(number="0009", source="feature", path="docs/adr/0009-b.md")]
    monkeypatch.setattr(check_records, "remote_claims", lambda branches, d: remote)
    assert evaluate(str(tmp_path), ["feature"]) == 1


def test_two_branches_same_path_is_a_collision(tmp_path, monkeypatch):
    # Both branches independently create docs/adr/0047-same.md. Keying on path
    # alone would dedupe to one; keying on (source, path) catches it.
    remote = [
        check_records.Claim(number="0047", source="branch-a", path="docs/adr/0047-same.md"),
        check_records.Claim(number="0047", source="branch-b", path="docs/adr/0047-same.md"),
    ]
    monkeypatch.setattr(check_records, "remote_claims", lambda branches, d: remote)
    assert evaluate(str(tmp_path), ["branch-a", "branch-b"]) == 1


def test_unreadable_branch_is_could_not_assess(tmp_path, monkeypatch):
    (tmp_path / "0001-a.md").write_text("x")
    monkeypatch.setattr(check_records, "remote_claims", lambda branches, d: None)
    assert evaluate(str(tmp_path), ["ghost-branch"]) == 2


def test_remote_claims_returns_none_when_git_fails(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(check_records.subprocess, "run", boom)
    assert check_records.remote_claims(["nope"], str(tmp_path)) is None
