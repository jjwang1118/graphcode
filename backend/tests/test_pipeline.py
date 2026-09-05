from pathlib import Path

import pytest

from app.models import EdgeType, NodeType
from app.pipeline import analyze


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path.resolve() / "sample"
    (root / "pkg").mkdir(parents=True)
    (root / "main.py").write_text("from pkg import helper\nimport requests\n")
    (root / "pkg" / "__init__.py").write_text("")
    (root / "pkg" / "helper.py").write_text("from . import sibling\n")
    (root / "pkg" / "sibling.py").write_text("")
    (root / "README.md").write_text("# 不會被 parse\n")
    return root


def edges_of(root: Path, edge_type: EdgeType) -> list[tuple[str, str]]:
    document = analyze(root).document()
    return [(e.source, e.target) for e in document.edges if e.type == edge_type]


def test_the_contains_half_still_covers_the_whole_tree(project: Path) -> None:
    assert set(edges_of(project, EdgeType.CONTAINS)) == {
        ("repo:.", "dir:pkg"),
        ("repo:.", "file:main.py"),
        ("repo:.", "file:README.md"),
        ("dir:pkg", "file:pkg/__init__.py"),
        ("dir:pkg", "file:pkg/helper.py"),
        ("dir:pkg", "file:pkg/sibling.py"),
    }


def test_imports_edges_reach_both_project_files_and_external_packages(
    project: Path,
) -> None:
    assert set(edges_of(project, EdgeType.IMPORTS)) == {
        ("file:main.py", "file:pkg/helper.py"),
        ("file:main.py", "ext:requests"),
        ("file:pkg/helper.py", "file:pkg/sibling.py"),
    }


def test_external_packages_join_the_graph_as_nodes(project: Path) -> None:
    document = analyze(project).document()

    external = [n for n in document.nodes if n.type == NodeType.EXTERNAL_PACKAGE]
    assert [(node.id, node.label) for node in external] == [
        ("ext:requests", "requests")
    ]


def test_a_file_with_no_parser_is_still_in_the_graph(project: Path) -> None:
    document = analyze(project).document()

    readme = next(node for node in document.nodes if node.id == "file:README.md")
    # 進圖但不 parse 是正常的，不算失敗
    assert readme.properties == {}
    assert document.meta.parse_failures == 0


def test_a_broken_file_is_marked_on_its_node_and_counted(project: Path) -> None:
    (project / "broken.py").write_text("def oops(:\n")

    document = analyze(project).document()

    node = next(node for node in document.nodes if node.id == "file:broken.py")
    assert "line 1" in node.properties["parse_error"]
    assert document.meta.parse_failures == 1


def test_a_broken_file_loses_its_imports_but_not_the_rest_of_the_graph(
    project: Path,
) -> None:
    (project / "broken.py").write_text("import requests\ndef oops(:\n")

    imports = edges_of(project, EdgeType.IMPORTS)

    assert not any(source == "file:broken.py" for source, _ in imports)
    assert ("file:main.py", "ext:requests") in imports


def test_a_circular_import_shows_up_in_meta(tmp_path: Path) -> None:
    root = tmp_path.resolve() / "loop"
    root.mkdir()
    (root / "a.py").write_text("import b\n")
    (root / "b.py").write_text("import a\n")

    assert analyze(root).document().meta.cycles == [["file:a.py", "file:b.py"]]


def test_the_view_keeps_only_the_edges_it_was_asked_for(project: Path) -> None:
    view = analyze(project).view(EdgeType.IMPORTS)

    assert {edge.type for edge in view.edges} == {EdgeType.IMPORTS}
    # 篩邊不會丟掉節點
    assert view.meta.node_count == analyze(project).document().meta.node_count
