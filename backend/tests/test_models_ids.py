import pytest

from app.models import PREFIX, NodeType, make_id, owner_file


def test_every_node_type_has_a_prefix() -> None:
    assert set(PREFIX) == set(NodeType)


def test_prefixes_are_unique() -> None:
    assert len(set(PREFIX.values())) == len(PREFIX)


def test_make_id_matches_the_documented_examples() -> None:
    assert make_id(NodeType.FILE, "src/app.py") == "file:src/app.py"
    assert make_id(NodeType.DIRECTORY, "src") == "dir:src"
    assert make_id(NodeType.EXTERNAL_PACKAGE, "fastapi") == "ext:fastapi"
    assert make_id(NodeType.REPO, ".") == "repo:."


def test_make_id_appends_member_after_the_file_path() -> None:
    assert make_id(NodeType.CLASS, "src/app.py", "Runner") == "class:src/app.py::Runner"
    assert (
        make_id(NodeType.FUNCTION, "src/app.py", "Runner.run")
        == "function:src/app.py::Runner.run"
    )


def test_make_id_normalizes_separators() -> None:
    assert make_id(NodeType.FILE, "src\\app.py") == "file:src/app.py"
    assert make_id(NodeType.DIRECTORY, "src/utils/") == "dir:src/utils"


@pytest.mark.parametrize("path", ["", "/", "/abs/app.py", "C:/src/app.py"])
def test_make_id_rejects_paths_that_are_not_relative_to_the_root(path: str) -> None:
    with pytest.raises(ValueError):
        make_id(NodeType.FILE, path)


def test_owner_file_reaches_back_to_the_file() -> None:
    assert owner_file("class:src/app.py::Runner") == "file:src/app.py"
    assert owner_file("function:src/app.py::Runner.run") == "file:src/app.py"
    assert owner_file("file:src/app.py") == "file:src/app.py"


@pytest.mark.parametrize(
    "node_id", ["dir:src", "ext:fastapi", "repo:.", "module:src/utils", "nonsense"]
)
def test_owner_file_returns_none_when_there_is_no_owning_file(node_id: str) -> None:
    assert owner_file(node_id) is None


def test_owner_file_round_trips_make_id() -> None:
    file_id = make_id(NodeType.FILE, "src/utils/io.py")
    assert owner_file(make_id(NodeType.FUNCTION, "src/utils/io.py", "read")) == file_id
