import json
from pathlib import Path

from scripts.check_review_evidence import (
    Verdict,
    evaluate,
    has_valid_review,
    latest_per_identity,
    verdicts_from_reviews,
)

HEAD = "headsha111111111111111111111111111111111"
OLD = "oldsha0000000000000000000000000000000000"
BOT = "reviewer-bot[bot]"

FIXTURE = Path(__file__).parent / "fixtures" / "reviews_rest_response.json"


def _fixture_verdicts():
    return verdicts_from_reviews(json.loads(FIXTURE.read_text()))


def test_maps_real_rest_shape():
    verdicts = _fixture_verdicts()
    assert Verdict(identity=BOT, state="APPROVED", commit_id=HEAD,
                   submitted_at="2026-08-27T12:00:00Z") in verdicts


def test_authorised_bot_latest_approval_bound_to_head_passes():
    verdicts = _fixture_verdicts()
    assert evaluate(verdicts, HEAD, {BOT})[0] == 0


def test_human_approval_of_old_sha_does_not_count():
    # The fixture's only head-bound approval is the bot's; the human approved OLD.
    verdicts = _fixture_verdicts()
    assert evaluate(verdicts, HEAD, {"dev-human"})[0] == 1


def test_unauthorised_identity_is_ignored():
    verdicts = _fixture_verdicts()
    # Nobody in the authorised set has any verdict at all.
    assert evaluate(verdicts, HEAD, {"someone-else"})[0] == 1


def test_latest_verdict_wins_a_later_rejection_revokes_approval():
    verdicts = [
        Verdict(BOT, "APPROVED", HEAD, "2026-08-27T12:00:00Z"),
        Verdict(BOT, "CHANGES_REQUESTED", HEAD, "2026-08-27T13:00:00Z"),
    ]
    assert not has_valid_review(verdicts, HEAD, {BOT})
    assert evaluate(verdicts, HEAD, {BOT})[0] == 1


def test_latest_per_identity_picks_most_recent():
    verdicts = [
        Verdict(BOT, "COMMENTED", HEAD, "2026-08-27T11:00:00Z"),
        Verdict(BOT, "APPROVED", HEAD, "2026-08-27T12:00:00Z"),
    ]
    latest = latest_per_identity(verdicts, {BOT})
    assert latest[BOT].state == "APPROVED"


def test_non_native_verdict_from_any_source_is_accepted():
    # A verdict that never came from a GitHub review (e.g. a reviewer App
    # publishing a check-run verdict) evaluates identically.
    verdicts = [Verdict("verdict-service", "APPROVED", HEAD, "2026-08-27T12:00:00Z")]
    assert evaluate(verdicts, HEAD, {"verdict-service"})[0] == 0


def test_missing_head_sha_is_could_not_assess():
    assert evaluate([], "", {BOT})[0] == 2


def test_no_authorised_set_is_could_not_assess():
    assert evaluate([Verdict(BOT, "APPROVED", HEAD, "t")], HEAD, set())[0] == 2


def test_review_without_commit_id_fails_safe():
    verdicts = verdicts_from_reviews([
        {"user": {"login": BOT}, "state": "APPROVED", "submitted_at": "t"}
    ])
    assert verdicts[0].commit_id == ""
    assert evaluate(verdicts, HEAD, {BOT})[0] == 1
