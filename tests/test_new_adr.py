from scripts.new_adr import create, next_number, slugify


def test_next_number_starts_at_0001_when_empty(tmp_path):
    assert next_number(tmp_path) == "0001"


def test_next_number_is_max_plus_one(tmp_path):
    (tmp_path / "0001-a.md").write_text("x")
    (tmp_path / "0007-b.md").write_text("x")
    assert next_number(tmp_path) == "0008"


def test_slugify():
    assert slugify("Use Postgres, not SQLite!") == "use-postgres-not-sqlite"


def test_create_writes_templated_file(tmp_path):
    path = create("Adopt the thing", adr_dir=tmp_path)
    assert path.name == "0001-adopt-the-thing.md"
    body = path.read_text()
    assert "# ADR-0001: Adopt the thing" in body
    assert "## Context" in body
    assert "## Decision" in body
    assert "## Consequences" in body
