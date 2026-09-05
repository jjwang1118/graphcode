import pytest

from app.graph import BuildError, build
from app.models import Edge, EdgeType, Node, NodeType


def _file(path: str) -> Node:
    return Node(id=f"file:{path}", type=NodeType.FILE, label=path)


def _imports(source: str, target: str) -> Edge:
    return Edge(source=f"file:{source}", target=f"file:{target}", type=EdgeType.IMPORTS)


def test_empty_input_builds_an_empty_graph() -> None:
    graph = build([], [])

    assert graph.meta.node_count == 0
    assert graph.meta.edge_count == 0


def test_counts_come_from_the_input() -> None:
    nodes = [
        Node(id="repo:.", type=NodeType.REPO, label="sample"),
        _file("app.py"),
    ]
    edges = [Edge(source="repo:.", target="file:app.py", type=EdgeType.CONTAINS)]

    graph = build(nodes, edges)

    assert graph.meta.node_count == 2
    assert graph.meta.edge_count == 1


def test_analyzed_at_is_filled_in() -> None:
    assert build([], []).meta.analyzed_at is not None


def test_dangling_edges_are_all_reported_at_once() -> None:
    nodes = [_file("app.py")]
    edges = [_imports("app.py", "missing.py"), _imports("gone.py", "app.py")]

    with pytest.raises(BuildError) as error:
        build(nodes, edges)

    assert "file:missing.py" in str(error.value)
    assert "file:gone.py" in str(error.value)


def test_duplicate_node_ids_are_rejected() -> None:
    with pytest.raises(BuildError) as error:
        build([_file("app.py"), _file("app.py")], [])

    assert "file:app.py" in str(error.value)


def test_parallel_edges_are_kept() -> None:
    nodes = [_file("app.py"), _file("io.py")]
    edges = [_imports("app.py", "io.py"), _imports("app.py", "io.py")]

    assert build(nodes, edges).meta.edge_count == 2


def test_import_cycles_are_detected() -> None:
    nodes = [_file("a.py"), _file("b.py")]
    edges = [_imports("a.py", "b.py"), _imports("b.py", "a.py")]

    assert build(nodes, edges).meta.cycles == [["file:a.py", "file:b.py"]]


def test_contains_edges_never_produce_cycles() -> None:
    nodes = [
        Node(id="repo:.", type=NodeType.REPO, label="sample"),
        Node(id="dir:src", type=NodeType.DIRECTORY, label="src"),
    ]
    edges = [Edge(source="repo:.", target="dir:src", type=EdgeType.CONTAINS)]

    assert build(nodes, edges).meta.cycles == []


def test_cycles_start_at_the_smallest_id_so_they_are_reproducible() -> None:
    nodes = [_file("a.py"), _file("b.py"), _file("c.py")]
    edges = [
        _imports("b.py", "c.py"),
        _imports("c.py", "a.py"),
        _imports("a.py", "b.py"),
    ]

    assert build(nodes, edges).meta.cycles == [["file:a.py", "file:b.py", "file:c.py"]]


def test_isolated_nodes_stay_empty_until_there_are_imports() -> None:
    assert build([_file("app.py")], []).meta.isolated_nodes == []


def test_networkx_is_not_exposed() -> None:
    graph = build([], [])

    assert [name for name in dir(graph) if not name.startswith("_")] == [
        "document",
        "meta",
        "view",
    ]
