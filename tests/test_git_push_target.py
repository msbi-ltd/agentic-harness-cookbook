import pytest

from scripts.git_push_target import classify

PROTECTED = {"main", "master"}


@pytest.mark.parametrize("cmd", [
    "git push origin main",
    "push origin main",
    "git push origin HEAD:main",
    "git push -f origin main",
    "git push --force origin feature:master",
    "git push origin +main",
    "git push origin refs/heads/main",
    "git push -u origin main",
])
def test_pushes_that_hit_a_protected_branch(cmd):
    assert classify(cmd.split()).could_hit(PROTECTED)


@pytest.mark.parametrize("cmd", [
    "git push origin feature",
    "git push origin HEAD:feature",
    "git push origin my-branch:their-branch",
])
def test_pushes_that_miss_protected_branches(cmd):
    assert not classify(cmd.split()).could_hit(PROTECTED)


@pytest.mark.parametrize("cmd", [
    "git push",                    # bare: depends on config we can't see
    "git push origin",             # no refspec: current branch's upstream
    "git push --all origin",       # many refs at once
    "git push --mirror origin",
])
def test_ambiguous_pushes_fail_closed(cmd):
    target = classify(cmd.split())
    assert target.unknown
    assert target.could_hit(PROTECTED)  # unknown must count as "could hit"


def test_push_option_value_is_not_mistaken_for_a_remote():
    # -o has a value; the real remote/refspec still follow.
    assert classify("git push -o ci.skip origin main".split()).could_hit(PROTECTED)


def test_force_with_lease_still_classified():
    assert classify("git push --force-with-lease origin main".split()).could_hit(PROTECTED)
