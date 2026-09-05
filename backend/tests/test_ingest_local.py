import os
from pathlib import Path

import pytest

from app.ingest import (
    ALLOWED_ROOTS_ENV,
    IngestError,
    allowed_roots_from_env,
    from_local_path,
)


@pytest.fixture
def allowed(tmp_path: Path) -> Path:
    root = tmp_path.resolve() / "allowed"
    (root / "project").mkdir(parents=True)
    return root


def test_accepts_a_directory_inside_the_allowlist(allowed: Path) -> None:
    assert from_local_path(str(allowed / "project"), [allowed]) == allowed / "project"


def test_accepts_the_allowlist_root_itself(allowed: Path) -> None:
    assert from_local_path(str(allowed), [allowed]) == allowed


def test_rejects_a_path_outside_the_allowlist(allowed: Path, tmp_path: Path) -> None:
    outside = tmp_path.resolve() / "outside"
    outside.mkdir()

    with pytest.raises(IngestError):
        from_local_path(str(outside), [allowed])


def test_rejects_parent_traversal(allowed: Path, tmp_path: Path) -> None:
    outside = tmp_path.resolve() / "outside"
    outside.mkdir()

    with pytest.raises(IngestError):
        from_local_path(str(allowed / ".." / "outside"), [allowed])


def test_rejects_a_sibling_that_shares_the_prefix(allowed: Path) -> None:
    sibling = allowed.with_name(allowed.name + "_other")
    sibling.mkdir()

    with pytest.raises(IngestError):
        from_local_path(str(sibling), [allowed])


def test_rejects_a_symlink_pointing_outside(allowed: Path, tmp_path: Path) -> None:
    outside = tmp_path.resolve() / "outside"
    outside.mkdir()
    link = allowed / "link"
    link.symlink_to(outside)

    with pytest.raises(IngestError):
        from_local_path(str(link), [allowed])


def test_rejects_everything_when_the_allowlist_is_empty(allowed: Path) -> None:
    with pytest.raises(IngestError):
        from_local_path(str(allowed / "project"), [])


def test_rejects_a_missing_path_inside_the_allowlist(allowed: Path) -> None:
    with pytest.raises(IngestError):
        from_local_path(str(allowed / "nope"), [allowed])


def test_rejects_a_file(allowed: Path) -> None:
    target = allowed / "project" / "app.py"
    target.write_text("")

    with pytest.raises(IngestError):
        from_local_path(str(target), [allowed])


def test_returns_a_resolved_path(allowed: Path) -> None:
    messy = allowed / "project" / ".." / "project"

    assert from_local_path(str(messy), [allowed]) == allowed / "project"


def test_allowlist_entries_are_resolved_before_comparing(
    allowed: Path, tmp_path: Path
) -> None:
    link_to_allowed = tmp_path.resolve() / "link_to_allowed"
    link_to_allowed.symlink_to(allowed)

    assert from_local_path(str(allowed), [link_to_allowed]) == allowed


def test_env_is_empty_when_unset() -> None:
    assert allowed_roots_from_env({}) == []


def test_env_is_empty_when_blank() -> None:
    assert allowed_roots_from_env({ALLOWED_ROOTS_ENV: ""}) == []


def test_env_splits_on_the_path_separator(tmp_path: Path) -> None:
    first = tmp_path.resolve() / "a"
    second = tmp_path.resolve() / "b"
    raw = os.pathsep.join([str(first), str(second)])

    assert allowed_roots_from_env({ALLOWED_ROOTS_ENV: raw}) == [first, second]


def test_env_ignores_blank_entries(tmp_path: Path) -> None:
    first = tmp_path.resolve() / "a"
    raw = os.pathsep.join(["", str(first), ""])

    assert allowed_roots_from_env({ALLOWED_ROOTS_ENV: raw}) == [first]
