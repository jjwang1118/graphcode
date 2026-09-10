from app.graph.declarations import to_nodes
from app.models import EdgeType, NodeType
from app.parsers import Defines, Fact, Import

FILE = "file:src/app.py"


def declare(*facts: Fact) -> tuple[list[str], list[tuple[str, str]]]:
    """回傳（節點 id 清單, (來源, 目標) 的邊清單），大多數斷言只在意這兩件事。"""
    result = to_nodes({FILE: list(facts)})

    return (
        [node.id for node in result.nodes],
        [(edge.source, edge.target) for edge in result.edges],
    )


def test_a_top_level_declaration_hangs_on_its_file() -> None:
    nodes, edges = declare(Defines(kind="function", name="run", parent=None, line=1))

    assert nodes == ["function:src/app.py::run"]
    assert edges == [(FILE, "function:src/app.py::run")]


def test_a_method_hangs_on_its_class_not_on_the_file() -> None:
    nodes, edges = declare(
        Defines(kind="class", name="Runner", parent=None, line=1),
        Defines(kind="function", name="run", parent="Runner", line=2),
    )

    assert nodes == ["class:src/app.py::Runner", "function:src/app.py::Runner.run"]
    assert edges == [
        (FILE, "class:src/app.py::Runner"),
        ("class:src/app.py::Runner", "function:src/app.py::Runner.run"),
    ]


def test_a_closure_hangs_on_the_function_around_it() -> None:
    _, edges = declare(
        Defines(kind="function", name="outer", parent=None, line=1),
        Defines(kind="function", name="inner", parent="outer", line=2),
    )

    assert edges[1] == (
        "function:src/app.py::outer",
        "function:src/app.py::outer.inner",
    )


def test_the_node_carries_the_bare_name_and_the_line() -> None:
    result = to_nodes(
        {
            FILE: [
                Defines(kind="class", name="Runner", parent=None, line=1),
                Defines(kind="function", name="run", parent="Runner", line=8),
            ]
        }
    )
    node = result.nodes[1]

    # label 是裸名，完整路徑在 id 裡——兩邊都寫 Runner.run 只是重複
    assert (node.label, node.type, node.properties) == (
        "run",
        NodeType.FUNCTION,
        {"line": 8},
    )


def test_every_edge_is_a_defines_edge_with_nothing_on_it() -> None:
    result = to_nodes({FILE: [Defines(kind="class", name="A", parent=None, line=1)]})

    assert result.edges[0].type == EdgeType.DEFINES
    # 行號在節點上，邊再放一份是重複
    assert result.edges[0].properties == {}


def test_imports_are_ignored_here() -> None:
    nodes, edges = declare(
        Import(module="os", level=0, name=None, alias=None, line=1),
        Defines(kind="function", name="run", parent=None, line=2),
    )

    assert nodes == ["function:src/app.py::run"]
    assert len(edges) == 1


# --- 同一個作用域內的同名宣告 -------------------------------------------------
#
# 不去重就是重複的節點 id，而 build() 對那個直接丟 BuildError——整次分析零結果。


def test_overloads_collapse_onto_the_implementation_not_the_first_stub() -> None:
    result = to_nodes(
        {
            FILE: [
                Defines(kind="function", name="f", parent=None, line=1, overload=True),
                Defines(kind="function", name="f", parent=None, line=4, overload=True),
                Defines(kind="function", name="f", parent=None, line=7),
            ]
        }
    )

    assert len(result.nodes) == 1
    # 挑第一筆的話這裡會是 1，跳過去看到的是 `...` 而不是實作
    assert result.nodes[0].properties == {"line": 7, "redefined_at": [1, 4]}


def test_a_property_and_its_setter_collapse_onto_the_getter() -> None:
    # getter 與 setter 都沒有 @overload，所以規則退回「第一筆」，那正是 getter
    result = to_nodes(
        {
            FILE: [
                Defines(kind="class", name="C", parent=None, line=1),
                Defines(kind="function", name="x", parent="C", line=2),
                Defines(kind="function", name="x", parent="C", line=6),
            ]
        }
    )

    assert result.nodes[1].properties == {"line": 2, "redefined_at": [6]}


def test_a_group_that_is_all_stubs_still_produces_a_node() -> None:
    # .pyi 風格：整組都是簽章，沒有實作可挑。讓節點消失比行號指到空殼更糟。
    result = to_nodes(
        {
            FILE: [
                Defines(kind="function", name="f", parent=None, line=1, overload=True),
                Defines(kind="function", name="f", parent=None, line=3, overload=True),
            ]
        }
    )

    assert len(result.nodes) == 1
    assert result.nodes[0].properties == {"line": 1, "redefined_at": [3]}


def test_only_one_edge_survives_a_collapsed_group() -> None:
    _, edges = declare(
        Defines(kind="function", name="f", parent=None, line=1, overload=True),
        Defines(kind="function", name="f", parent=None, line=3),
    )

    assert edges == [(FILE, "function:src/app.py::f")]


def test_a_class_and_a_function_of_the_same_name_do_not_collide() -> None:
    # id 的前綴不同，所以是兩個節點——不需要去重
    nodes, _ = declare(
        Defines(kind="class", name="F", parent=None, line=1),
        Defines(kind="function", name="F", parent=None, line=5),
    )

    assert nodes == ["class:src/app.py::F", "function:src/app.py::F"]


def test_same_name_in_two_files_stays_two_nodes() -> None:
    result = to_nodes(
        {
            "file:a.py": [Defines(kind="function", name="parse", parent=None, line=1)],
            "file:b.py": [Defines(kind="function", name="parse", parent=None, line=1)],
        }
    )

    assert [node.id for node in result.nodes] == [
        "function:a.py::parse",
        "function:b.py::parse",
    ]


def test_nothing_in_nothing_out() -> None:
    assert to_nodes({}) == to_nodes({FILE: []})
