import pytest

from app.graph import CodeGraph, build
from app.models import Edge, EdgeType, Node, NodeType


@pytest.fixture
def graph() -> CodeGraph:
    nodes = [
        Node(id="repo:.", type=NodeType.REPO, label="sample"),
        Node(id="dir:src", type=NodeType.DIRECTORY, label="src"),
        Node(id="file:src/app.py", type=NodeType.FILE, label="app.py"),
        Node(id="file:src/io.py", type=NodeType.FILE, label="io.py"),
    ]
    edges = [
        Edge(source="repo:.", target="dir:src", type=EdgeType.CONTAINS),
        Edge(source="dir:src", target="file:src/app.py", type=EdgeType.CONTAINS),
        Edge(source="dir:src", target="file:src/io.py", type=EdgeType.CONTAINS),
        Edge(source="file:src/app.py", target="file:src/io.py", type=EdgeType.IMPORTS),
    ]
    return build(nodes, edges)


def test_document_returns_everything(graph: CodeGraph) -> None:
    document = graph.document()

    assert len(document.nodes) == 4
    assert len(document.edges) == 4


def test_view_keeps_only_the_requested_edge_types(graph: CodeGraph) -> None:
    tree = graph.view(EdgeType.CONTAINS)

    assert {edge.type for edge in tree.edges} == {EdgeType.CONTAINS}
    assert len(tree.edges) == 3


def test_the_dependency_view_is_the_same_graph_filtered(graph: CodeGraph) -> None:
    dependencies = graph.view(EdgeType.IMPORTS)

    assert [(edge.source, edge.target) for edge in dependencies.edges] == [
        ("file:src/app.py", "file:src/io.py")
    ]


def test_view_keeps_every_node(graph: CodeGraph) -> None:
    # 「這個檔案存在但沒有人 import 它」本身就是資訊，不能因為篩邊而消失。
    assert len(graph.view(EdgeType.IMPORTS).nodes) == 4


def test_view_counts_follow_the_view(graph: CodeGraph) -> None:
    tree = graph.view(EdgeType.CONTAINS)

    assert tree.meta.node_count == 4
    assert tree.meta.edge_count == 3


def test_view_carries_over_the_analysis_wide_meta(graph: CodeGraph) -> None:
    tree = graph.view(EdgeType.CONTAINS)

    assert tree.meta.analyzed_at == graph.meta.analyzed_at
    assert tree.meta.cycles == graph.meta.cycles


def test_view_without_types_is_the_whole_graph(graph: CodeGraph) -> None:
    assert graph.view() == graph.document()


def test_returns_models_not_networkx_objects(graph: CodeGraph) -> None:
    document = graph.document()

    assert all(isinstance(node, Node) for node in document.nodes)
    assert all(isinstance(edge, Edge) for edge in document.edges)
