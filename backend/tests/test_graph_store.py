from pathlib import Path

import pytest

from app.graph import BuildError, CodeGraph, build, load, save
from app.models import Edge, EdgeType, GraphDocument, Node, NodeType


@pytest.fixture
def graph() -> CodeGraph:
    nodes = [
        Node(id="repo:.", type=NodeType.REPO, label="sample"),
        Node(id="file:app.py", type=NodeType.FILE, label="app.py"),
    ]
    edges = [Edge(source="repo:.", target="file:app.py", type=EdgeType.CONTAINS)]
    return build(nodes, edges)


def test_round_trip_preserves_the_document(graph: CodeGraph, tmp_path: Path) -> None:
    target = tmp_path / "graph.json"
    save(graph, target)

    assert load(target).document() == graph.document()


def test_reading_back_runs_the_same_validation(tmp_path: Path) -> None:
    # 手工寫一份壞掉的檔案：邊指向不存在的節點。
    broken = GraphDocument(
        nodes=[Node(id="file:app.py", type=NodeType.FILE, label="app.py")],
        edges=[
            Edge(source="file:app.py", target="file:gone.py", type=EdgeType.IMPORTS)
        ],
    )
    target = tmp_path / "broken.json"
    target.write_text(broken.model_dump_json(), encoding="utf-8")

    with pytest.raises(BuildError):
        load(target)


def test_reading_back_keeps_the_original_analysis_time(
    graph: CodeGraph, tmp_path: Path
) -> None:
    target = tmp_path / "graph.json"
    save(graph, target)

    assert load(target).meta.analyzed_at == graph.meta.analyzed_at
