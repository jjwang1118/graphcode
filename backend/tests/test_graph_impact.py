"""影響範圍：`CodeGraph.impact()`（查詢層）、`project()`（換到畫面的層級）、
`POST /api/impact`（plan 5.6 第二段）。

同一個小專案貫穿全部：

    repo:.
    └── dir:src
        ├── file:src/app.py   export、main、other
        └── file:src/io.py    save

    save ← export ← main        （main 呼叫 export，export 呼叫 save）
    save ← other                 other 也直接呼叫 save
    export ← other               同一層互相呼叫，不是擴散的路徑
"""

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.impact import ImpactRequest, impact
from app.graph import CodeGraph, UnknownNodeError, build, project
from app.ingest import ALLOWED_ROOTS_ENV
from app.models import Edge, EdgeType, GraphDocument, Node, NodeType

APP = "file:src/app.py"
IO = "file:src/io.py"
SAVE = "function:src/io.py::save"
EXPORT = "function:src/app.py::export"
MAIN = "function:src/app.py::main"
OTHER = "function:src/app.py::other"


def _node(node_id: str) -> Node:
    kind = {
        "repo": NodeType.REPO,
        "dir": NodeType.DIRECTORY,
        "file": NodeType.FILE,
        "function": NodeType.FUNCTION,
    }[node_id.split(":", 1)[0]]
    return Node(id=node_id, type=kind, label=node_id.rsplit(":", 1)[-1])


@pytest.fixture
def graph() -> CodeGraph:
    ids = ["repo:.", "dir:src", APP, IO, SAVE, EXPORT, MAIN, OTHER]
    edges = [
        ("repo:.", "dir:src", EdgeType.CONTAINS),
        ("dir:src", APP, EdgeType.CONTAINS),
        ("dir:src", IO, EdgeType.CONTAINS),
        (IO, SAVE, EdgeType.DEFINES),
        (APP, EXPORT, EdgeType.DEFINES),
        (APP, MAIN, EdgeType.DEFINES),
        (APP, OTHER, EdgeType.DEFINES),
        (EXPORT, SAVE, EdgeType.CALLS),
        (MAIN, EXPORT, EdgeType.CALLS),
        (OTHER, SAVE, EdgeType.CALLS),
        (OTHER, EXPORT, EdgeType.CALLS),
    ]
    return build(
        [_node(node_id) for node_id in ids],
        [Edge(source=s, target=t, type=kind) for s, t, kind in edges],
    )


def depths(document: GraphDocument) -> dict[str, int]:
    return {node.id: node.properties["impact_depth"] for node in document.nodes}


def pairs(document: GraphDocument) -> set[tuple[str, str]]:
    return {(edge.source, edge.target) for edge in document.edges}


# --- 查詢層 ---------------------------------------------------------------------


def test_the_impact_walks_every_caller_all_the_way_up(graph: CodeGraph) -> None:
    affected = graph.impact(SAVE)

    assert depths(affected) == {SAVE: 0, EXPORT: 1, OTHER: 1, MAIN: 2}


def test_only_the_steps_outward_are_kept_as_edges(graph: CodeGraph) -> None:
    # other → export 兩端都在第 1 層，不是波及的路徑
    assert pairs(graph.impact(SAVE)) == {(EXPORT, SAVE), (OTHER, SAVE), (MAIN, EXPORT)}


def test_clicking_a_file_starts_from_everything_it_declares(graph: CodeGraph) -> None:
    assert depths(graph.impact(IO)) == {IO: 0, SAVE: 0, EXPORT: 1, OTHER: 1, MAIN: 2}


def test_a_function_nobody_calls_affects_only_itself(graph: CodeGraph) -> None:
    affected = graph.impact(MAIN)

    assert depths(affected) == {MAIN: 0}
    assert affected.edges == []


def test_an_unknown_node_is_loud(graph: CodeGraph) -> None:
    with pytest.raises(UnknownNodeError):
        graph.impact("function:nowhere.py::ghost")


# --- 換到畫面的層級 ---------------------------------------------------------------


def test_without_a_level_the_projection_changes_nothing(graph: CodeGraph) -> None:
    projected = project(graph.impact(SAVE), graph.document())

    assert depths(projected) == depths(graph.impact(SAVE))


def test_collapsed_nodes_light_up_at_their_earliest_step(graph: CodeGraph) -> None:
    # level=2 是檔案層：四個函式收進兩個檔案。app.py 裡最早被波及的是第 1 步
    projected = project(graph.impact(SAVE), graph.document(), level=2)

    assert depths(projected) == {IO: 0, APP: 1}


def test_collapsed_edges_merge_and_self_loops_disappear(graph: CodeGraph) -> None:
    projected = project(graph.impact(SAVE), graph.document(), level=2)

    # export→save 與 other→save 合成一條；main→export 收進同一個檔案，不畫
    assert [(e.source, e.target, e.properties["weight"]) for e in projected.edges] == [
        (APP, IO, 2)
    ]


# --- API ------------------------------------------------------------------------


@pytest.fixture
def project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path.resolve() / "project"
    (root / "src").mkdir(parents=True)
    (root / "src" / "io.py").write_text("def save(): ...\n")
    (root / "src" / "app.py").write_text(
        "from src.io import save\n\n"
        "def export():\n    save()\n\n"
        "def main():\n    export()\n"
    )
    monkeypatch.setenv(ALLOWED_ROOTS_ENV, str(root))
    return root


def test_the_endpoint_answers_from_a_real_project(project_root: Path) -> None:
    answer = impact(ImpactRequest(path=str(project_root), node=SAVE))

    assert depths(answer) == {SAVE: 0, EXPORT: 1, MAIN: 2}


def test_the_endpoint_uses_the_same_level_as_the_screen(project_root: Path) -> None:
    answer = impact(ImpactRequest(path=str(project_root), node=IO, level=2))

    assert depths(answer) == {IO: 0, APP: 1}


def test_an_unknown_node_becomes_404(project_root: Path) -> None:
    with pytest.raises(HTTPException) as error:
        impact(ImpactRequest(path=str(project_root), node="file:src/ghost.py"))

    assert error.value.status_code == 404
