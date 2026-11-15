import json

import pytest

from scripts.generate_release_notes import Commit, group_sections, upsert


PRODUCT = ("service/", "web/src/")
EXCLUDED = ("web/src/generated-release-notes/",)


def test_groups_only_product_facing_conventional_commits():
    commits = [
        Commit("feat(search): add saved filters (#42)", ("web/src/Search.tsx",)),
        Commit("fix(ci): retry registry login (#43)", (".github/workflows/ci.yml",)),
        Commit("fix(api): reject an invalid cursor (#44)", ("service/routes/search.py",)),
        Commit("docs: explain saved filters", ("README.md",)),
    ]

    assert group_sections(commits, PRODUCT, EXCLUDED) == [
        {"heading": "Features", "items": ["add saved filters (#42)"]},
        {"heading": "Fixes", "items": ["reject an invalid cursor (#44)"]},
    ]


def test_generated_notes_do_not_classify_the_generator_as_product_work():
    commits = [
        Commit(
            "fix(release): make notes generation idempotent",
            ("scripts/generate_release_notes.py", "web/src/generated-release-notes/notes.json"),
        )
    ]

    assert group_sections(commits, PRODUCT, EXCLUDED) == []


def test_breaking_footer_wins_over_commit_type():
    commits = [
        Commit(
            "feat(api): rename the query field\n\nBREAKING CHANGE: old field removed",
            ("service/routes/search.py",),
        )
    ]

    assert group_sections(commits, PRODUCT) == [
        {"heading": "Breaking", "items": ["rename the query field"]}
    ]


def test_upsert_is_idempotent_and_keeps_sorted_json(tmp_path):
    output = tmp_path / "notes.json"
    entry = {
        "version": "1.4.0",
        "released_at": "2026-09-04",
        "source": {"base": "abc123", "head": "def456"},
        "sections": [{"heading": "Features", "items": ["add saved filters"]}],
    }

    upsert(output, entry)
    first = output.read_text()
    upsert(output, entry)

    assert output.read_text() == first
    assert json.loads(first)["1.4.0"]["source"]["head"] == "def456"


def test_empty_rerun_cannot_erase_existing_notes(tmp_path):
    output = tmp_path / "notes.json"
    upsert(
        output,
        {
            "version": "1.4.0",
            "released_at": "2026-09-04",
            "source": {"base": "abc123", "head": "def456"},
            "sections": [{"heading": "Fixes", "items": ["repair export"]}],
        },
    )

    with pytest.raises(ValueError, match="refusing to replace"):
        upsert(
            output,
            {
                "version": "1.4.0",
                "released_at": "2026-09-04",
                "source": {"base": "def456", "head": "def456"},
                "sections": [],
            },
        )
