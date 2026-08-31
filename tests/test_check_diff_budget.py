from scripts.check_diff_budget import escape_grant, evaluate_diff_budget


def test_within_budget():
    ok, detail = evaluate_diff_budget(files=3, additions=100, deletions=40, labels=[])
    assert ok
    assert "within budget" in detail


def test_over_net_lines():
    ok, detail = evaluate_diff_budget(files=2, additions=600, deletions=10, labels=[])
    assert not ok
    assert "over budget" in detail


def test_equal_size_rewrite_caught_by_churn_even_though_net_is_zero():
    # 1000 added, 1000 deleted -> net 0 (would slip a net-only check) but churn 2000.
    ok, detail = evaluate_diff_budget(files=2, additions=1000, deletions=1000, labels=[])
    assert not ok
    assert "churn" in detail


def test_over_file_count():
    ok, _ = evaluate_diff_budget(files=20, additions=10, deletions=0, labels=[])
    assert not ok


def test_escape_label_overrides_over_budget():
    ok, detail = evaluate_diff_budget(
        files=2, additions=1000, deletions=1000, labels=["oversize-approved"]
    )
    assert ok
    assert "approved" in detail


def test_large_deletion_only_caught_by_abs_net():
    # -700 net; abs() is what catches a big pure deletion.
    ok, _ = evaluate_diff_budget(files=1, additions=0, deletions=700, labels=[])
    assert not ok


def test_label_from_authorised_actor_grants_the_exception():
    ok, detail = evaluate_diff_budget(
        files=2, additions=1000, deletions=1000, labels=["oversize-approved"],
        granting_actor="maintainer", authorised_actors={"maintainer"},
    )
    assert ok
    assert "authorised actor" in detail


def test_label_from_unauthorised_actor_does_not_grant():
    ok, detail = evaluate_diff_budget(
        files=2, additions=1000, deletions=1000, labels=["oversize-approved"],
        granting_actor="the-authoring-agent", authorised_actors={"maintainer"},
    )
    assert not ok
    assert "not in the authorised set" in detail


def test_label_without_actor_verification_is_accepted_but_flagged():
    granted, why = escape_grant(["oversize-approved"])
    assert granted
    assert "NOT verified" in why


def test_no_label_is_not_a_grant():
    granted, why = escape_grant([], granting_actor="anyone", authorised_actors={"maintainer"})
    assert not granted
