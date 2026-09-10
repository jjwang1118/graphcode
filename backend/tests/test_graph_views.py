import pytest

from app.graph import collapse, only_edges
from app.models import Edge, EdgeType, GraphDocument, Node, NodeType

# repo:.
# ├── dir:a
# │   ├── dir:a/b
# │   │   ├── file:a/b/one.py
# │   │   └── file:a/b/two.py
# │   └── file:a/solo.py
# └── file:README.md
TREE = [
    ("repo:.", "dir:a"),
    ("repo:.", "file:README.md"),
    ("dir:a", "dir:a/b"),
    ("dir:a", "file:a/solo.py"),
    ("dir:a/b", "file:a/b/one.py"),
    ("dir:a/b", "file:a/b/two.py"),
]


def node(node_id: str) -> Node:
    kind = {
        "repo": NodeType.REPO,
        "dir": NodeType.DIRECTORY,
        "file": NodeType.FILE,
        "ext": NodeType.EXTERNAL_PACKAGE,
    }[node_id.split(":", 1)[0]]
    return Node(id=node_id, type=kind, label=node_id.split(":", 1)[1].split("/")[-1])


def document(
    imports: list[tuple[str, str]], externals: list[str] | None = None
) -> GraphDocument:
    ids = {end for edge in TREE for end in edge} | set(externals or [])
    return GraphDocument(
        nodes=[node(node_id) for node_id in sorted(ids)],
        edges=[
            *(
                Edge(source=source, target=target, type=EdgeType.CONTAINS)
                for source, target in TREE
            ),
            *(
                Edge(source=source, target=target, type=EdgeType.IMPORTS)
                for source, target in imports
            ),
        ],
    )


def ids(result: GraphDocument) -> set[str]:
    return {node.id for node in result.nodes}


def imports_of(result: GraphDocument) -> dict[tuple[str, str], int]:
    return {
        (edge.source, edge.target): edge.properties["weight"]
        for edge in result.edges
        if edge.type == EdgeType.IMPORTS
    }


# ── 收合層級 ─────────────────────────────────────────────────────


def test_no_level_leaves_the_document_alone() -> None:
    original = document([("file:a/b/one.py", "file:a/solo.py")])

    assert collapse(original) is original


def test_level_one_keeps_only_the_top_layer() -> None:
    result = collapse(document([]), level=1)

    assert ids(result) == {"repo:.", "dir:a", "file:README.md"}


def test_a_node_too_shallow_to_collapse_keeps_itself() -> None:
    # README.md 在根目錄下，level=2 時它上面沒有兩層目錄
    result = collapse(document([]), level=2)

    assert "file:README.md" in ids(result)


def test_declarations_collapse_into_the_file_they_live_in() -> None:
    # 層級樹要吃 contains ＋ defines。只認 contains 的話 class / function 上面
    # 沒有父節點，會被當成深度 0 的孤兒，每個層級都收不掉。
    original = document([])
    original.nodes.append(
        Node(id="function:a/b/one.py::run", type=NodeType.FUNCTION, label="run")
    )
    original.edges.append(
        Edge(
            source="file:a/b/one.py",
            target="function:a/b/one.py::run",
            type=EdgeType.DEFINES,
        )
    )

    # one.py 在第 3 層，它的函式就在第 4 層
    assert "function:a/b/one.py::run" not in ids(collapse(original, level=3))
    assert "function:a/b/one.py::run" in ids(collapse(original, level=4))


def test_imports_between_collapsed_groups_become_one_weighted_edge() -> None:
    original = document(
        [
            ("file:a/b/one.py", "file:README.md"),
            ("file:a/b/two.py", "file:README.md"),
        ]
    )

    result = collapse(original, level=1)

    assert imports_of(result) == {("dir:a", "file:README.md"): 2}


def test_imports_inside_one_group_are_counted_on_the_node_not_drawn() -> None:
    original = document([("file:a/b/one.py", "file:a/b/two.py")])

    result = collapse(original, level=1)

    assert imports_of(result) == {}
    collapsed = next(node for node in result.nodes if node.id == "dir:a")
    assert collapsed.properties["internal_imports"] == 1


def test_collapsed_imports_keep_the_edges_they_swallowed() -> None:
    original = document(
        [
            ("file:a/b/one.py", "file:README.md"),
            ("file:a/b/two.py", "file:README.md"),
        ]
    )

    result = collapse(original, level=1)

    edge = next(edge for edge in result.edges if edge.type == EdgeType.IMPORTS)
    assert edge.properties["weight"] == len(edge.properties["sources"])
    assert [(one["from"], one["to"]) for one in edge.properties["sources"]] == [
        ("file:a/b/one.py", "file:README.md"),
        ("file:a/b/two.py", "file:README.md"),
    ]


def test_collapsed_imports_carry_the_original_properties() -> None:
    original = document([])
    original.edges.append(
        Edge(
            source="file:a/b/one.py",
            target="file:README.md",
            type=EdgeType.IMPORTS,
            properties={"module": "README", "name": "thing", "line": 12},
        )
    )

    result = collapse(original, level=1)

    edge = next(edge for edge in result.edges if edge.type == EdgeType.IMPORTS)
    assert edge.properties["sources"] == [
        {
            "from": "file:a/b/one.py",
            "to": "file:README.md",
            "module": "README",
            "name": "thing",
            "line": 12,
        }
    ]


def test_contains_edges_do_not_carry_sources() -> None:
    # 目錄的細節換個層級就看得到，揹著只是讓 JSON 變大
    result = collapse(document([]), level=1)

    contains = [edge for edge in result.edges if edge.type == EdgeType.CONTAINS]
    assert contains
    assert all("sources" not in edge.properties for edge in contains)


def test_sources_remember_which_package_each_edge_pointed_at() -> None:
    # grouped 把套件併成一個節點，`to` 是唯一還留著「原本指向誰」的地方
    original = document(
        [("file:a/solo.py", "ext:torch"), ("file:a/solo.py", "ext:numpy")],
        externals=["ext:torch", "ext:numpy"],
    )

    result = collapse(original, externals="grouped")

    edge = next(edge for edge in result.edges if edge.target == "ext:*")
    assert [one["to"] for one in edge.properties["sources"]] == [
        "ext:torch",
        "ext:numpy",
    ]


def test_meta_counts_follow_the_collapsed_graph() -> None:
    result = collapse(document([]), level=1)

    assert result.meta.node_count == len(result.nodes)
    assert result.meta.edge_count == len(result.edges)


# ── 外部套件 ─────────────────────────────────────────────────────


def test_full_keeps_every_package_as_its_own_node() -> None:
    original = document([("file:a/solo.py", "ext:torch")], externals=["ext:torch"])

    assert "ext:torch" in ids(collapse(original, level=1, externals="full"))


def test_grouped_merges_every_package_into_one_node() -> None:
    original = document(
        [("file:a/solo.py", "ext:torch"), ("file:a/b/one.py", "ext:numpy")],
        externals=["ext:torch", "ext:numpy"],
    )

    result = collapse(original, level=1, externals="grouped")

    assert "ext:torch" not in ids(result)
    grouped = next(node for node in result.nodes if node.id == "ext:*")
    # 名單留著，之後要做「點開展開」不必重新分析
    assert grouped.properties["packages"] == ["numpy", "torch"]
    assert imports_of(result) == {("dir:a", "ext:*"): 2}


def test_hidden_drops_the_packages_and_the_edges_reaching_them() -> None:
    original = document(
        [("file:a/solo.py", "ext:torch"), ("file:a/b/one.py", "file:README.md")],
        externals=["ext:torch"],
    )

    result = collapse(original, level=1, externals="hidden")

    assert not any(node.id.startswith("ext:") for node in result.nodes)
    assert imports_of(result) == {("dir:a", "file:README.md"): 1}


def test_hiding_packages_works_without_collapsing() -> None:
    original = document([("file:a/solo.py", "ext:torch")], externals=["ext:torch"])

    result = collapse(original, externals="hidden")

    assert "ext:torch" not in ids(result)
    assert "file:a/solo.py" in ids(result)


# ── 篩邊 ─────────────────────────────────────────────────────────


def test_only_edges_keeps_every_node() -> None:
    original = document([("file:a/solo.py", "file:README.md")])

    result = only_edges(original, [EdgeType.IMPORTS])

    assert ids(result) == ids(original)
    assert {edge.type for edge in result.edges} == {EdgeType.IMPORTS}
    assert result.meta.edge_count == 1


@pytest.mark.parametrize("level", [0, 1, 2])
def test_collapsing_never_leaves_an_edge_pointing_nowhere(level: int) -> None:
    original = document(
        [("file:a/b/one.py", "ext:torch"), ("file:a/solo.py", "file:README.md")],
        externals=["ext:torch"],
    )

    result = collapse(original, level=level, externals="grouped")

    known = ids(result)
    assert all(edge.source in known and edge.target in known for edge in result.edges)
