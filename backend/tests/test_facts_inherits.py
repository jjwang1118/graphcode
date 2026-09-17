"""繼承事實 → `inherits` 邊（H1–H4）。

產生器本身很薄——查表的難處在 `test_resolve_names.py`。這裡管的是接出來的邊長
得對不對，以及**查不到時不亂連**。
"""

from collections.abc import Mapping, Sequence

from app.facts import InheritsProducer
from app.facts.production import Context
from app.languages import LANGUAGES
from app.models import EdgeType
from app.parsers import Defines, Fact, Import, Inherits
from app.resolve import PythonResolver, from_facts, from_files

APP = "file:src/app.py"
LIB = "file:src/lib.py"


def produce(
    facts: Mapping[str, Sequence[Fact]],
) -> tuple[list[tuple[str, str]], int]:
    """回傳（(來源, 目標) 的邊清單, unresolved 計數）。"""
    index = from_files(["src/app.py", "src/lib.py"])
    names = from_facts(facts, index, PythonResolver())
    mine = {
        file_id: [one for one in facts[file_id] if isinstance(one, Inherits)]
        for file_id in facts
    }
    produced = InheritsProducer().produce(
        {k: v for k, v in mine.items() if v},
        Context(index=index, language=LANGUAGES[".py"], names=names),
    )

    assert all(edge.type is EdgeType.INHERITS for edge in produced.edges)
    return (
        [(edge.source, edge.target) for edge in produced.edges],
        produced.counters["unresolved_inherits"],
    )


def test_a_base_declared_in_the_same_file_becomes_an_edge() -> None:
    edges, unresolved = produce(
        {
            APP: [
                Defines(kind="class", name="Base", parent=None, line=1),
                Defines(kind="class", name="Runner", parent=None, line=4),
                Inherits(child="Runner", base="Base", line=4),
            ]
        }
    )

    assert edges == [("class:src/app.py::Runner", "class:src/app.py::Base")]
    assert unresolved == 0


def test_a_base_imported_from_another_file_crosses_the_file_boundary() -> None:
    edges, _ = produce(
        {
            APP: [
                Import(module="src.lib", level=0, name="Base", alias=None, line=1),
                Defines(kind="class", name="Runner", parent=None, line=3),
                Inherits(child="Runner", base="Base", line=3),
            ],
            LIB: [Defines(kind="class", name="Base", parent=None, line=1)],
        }
    )

    assert edges == [("class:src/app.py::Runner", "class:src/lib.py::Base")]


def test_a_nested_class_hangs_off_its_full_path() -> None:
    edges, _ = produce(
        {
            APP: [
                Defines(kind="class", name="Base", parent=None, line=1),
                Defines(kind="class", name="Outer", parent=None, line=4),
                Defines(kind="class", name="Inner", parent="Outer", line=5),
                Inherits(child="Outer.Inner", base="Base", line=5),
            ]
        }
    )

    assert edges == [("class:src/app.py::Outer.Inner", "class:src/app.py::Base")]


def test_a_base_that_is_not_in_the_project_produces_no_edge() -> None:
    """builtins 與外部套件都走這條路——`inherits` 只連專案內的 class。"""
    edges, unresolved = produce(
        {
            APP: [
                Defines(kind="class", name="Error", parent=None, line=1),
                Inherits(child="Error", base="Exception", line=1),
            ]
        }
    )

    assert edges == []
    assert unresolved == 1


def test_a_name_that_resolves_to_a_function_is_not_inherited_from() -> None:
    """繼承只能是 class → class，接到函式節點會是一條假邊。"""
    edges, unresolved = produce(
        {
            APP: [
                Import(module="src.lib", level=0, name="thing", alias=None, line=1),
                Defines(kind="class", name="Runner", parent=None, line=3),
                Inherits(child="Runner", base="thing", line=3),
            ],
            LIB: [Defines(kind="function", name="thing", parent=None, line=1)],
        }
    )

    assert edges == []
    assert unresolved == 1


def test_the_edge_records_the_base_as_it_was_written() -> None:
    index = from_files(["src/app.py", "src/lib.py"])
    facts: dict[str, list[Fact]] = {
        APP: [
            Import(module="src", level=0, name="lib", alias=None, line=1),
            Defines(kind="class", name="Runner", parent=None, line=3),
        ],
        LIB: [Defines(kind="class", name="Base", parent=None, line=1)],
    }
    names = from_facts(facts, index, PythonResolver())

    produced = InheritsProducer().produce(
        {APP: [Inherits(child="Runner", base="lib.Base", line=3)]},
        Context(index=index, language=LANGUAGES[".py"], names=names),
    )

    # 寫的是 lib.Base、接到的是 src/lib.py 裡的 Base——兩個都留著才看得出接對沒有
    assert produced.edges[0].properties == {"base": "lib.Base", "line": 3}


def test_the_counter_is_always_there_even_at_zero() -> None:
    _, unresolved = produce(
        {APP: [Defines(kind="class", name="X", parent=None, line=1)]}
    )

    assert unresolved == 0
