from collections import Counter
from pathlib import Path

import pytest

from app.models import EdgeType, NodeType
from app.scan import from_root


@pytest.fixture
def sample(tmp_path: Path) -> Path:
    root = tmp_path.resolve() / "sample"
    (root / "src" / "__pycache__").mkdir(parents=True)
    (root / "src" / "app.py").write_text("")
    (root / "src" / "__pycache__" / "app.cpython-311.pyc").write_text("")
    (root / "README.md").write_text("")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("")
    return root


def test_nodes_cover_the_whole_tree(sample: Path) -> None:
    result = from_root(sample)

    assert {node.id for node in result.nodes} == {
        "repo:.",
        "dir:src",
        "file:src/app.py",
        "file:README.md",
    }


def test_repo_node_is_labelled_with_the_directory_name(sample: Path) -> None:
    repo = next(node for node in from_root(sample).nodes if node.type == NodeType.REPO)

    assert repo.label == "sample"


def test_edges_connect_each_node_to_its_direct_parent(sample: Path) -> None:
    result = from_root(sample)

    assert {(edge.source, edge.target) for edge in result.edges} == {
        ("repo:.", "dir:src"),
        ("repo:.", "file:README.md"),
        ("dir:src", "file:src/app.py"),
    }
    assert all(edge.type == EdgeType.CONTAINS for edge in result.edges)


def test_contains_edges_form_a_tree(sample: Path) -> None:
    result = from_root(sample)
    parents = Counter(edge.target for edge in result.edges)

    assert len(result.edges) == len(result.nodes) - 1
    assert all(count == 1 for count in parents.values())
    assert "repo:." not in parents


def test_ignored_directories_produce_no_nodes_at_all(sample: Path) -> None:
    ids = {node.id for node in from_root(sample).nodes}

    assert not any("__pycache__" in node_id or ".git" in node_id for node_id in ids)


def test_the_ignore_list_is_a_parameter(sample: Path) -> None:
    ids = {node.id for node in from_root(sample, ignore={"src", ".git"}).nodes}

    assert ids == {"repo:.", "file:README.md"}


def test_symlinks_are_skipped(sample: Path, tmp_path: Path) -> None:
    outside = tmp_path.resolve() / "outside"
    (outside / "secret").mkdir(parents=True)
    (outside / "secret.txt").write_text("")
    (sample / "link_dir").symlink_to(outside)
    (sample / "link_file").symlink_to(outside / "secret.txt")

    ids = {node.id for node in from_root(sample).nodes}

    assert not any("link" in node_id for node_id in ids)


def test_empty_directories_still_get_a_node(sample: Path) -> None:
    (sample / "empty").mkdir()

    ids = {node.id for node in from_root(sample).nodes}

    assert "dir:empty" in ids


def test_result_is_deterministic(sample: Path) -> None:
    assert from_root(sample) == from_root(sample)


def test_files_lists_every_file_node(sample: Path) -> None:
    result = from_root(sample)

    assert sorted(result.files) == sorted(
        node.id.removeprefix("file:")
        for node in result.nodes
        if node.type == NodeType.FILE
    )


def test_nested_directories_keep_their_relative_path(sample: Path) -> None:
    (sample / "src" / "utils").mkdir()
    (sample / "src" / "utils" / "io.py").write_text("")

    ids = {node.id for node in from_root(sample).nodes}

    assert {"dir:src/utils", "file:src/utils/io.py"} <= ids
