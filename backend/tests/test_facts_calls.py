"""呼叫事實 → `calls` 邊（K1–K5）。

產生器本身很薄——查表的難處在 `test_resolve_names.py`。這裡管的是接出來的邊長
得對不對、`self` 與建構子怎麼接，以及**查不到時不亂連**。
"""

from collections.abc import Mapping, Sequence

from app.facts import CallsProducer
from app.facts.production import Context
from app.languages import LANGUAGES
from app.models import EdgeType
from app.parsers import Calls, Defines, Fact, Import
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
        file_id: [one for one in facts[file_id] if isinstance(one, Calls)]
        for file_id in facts
    }
    produced = CallsProducer().produce(
        {k: v for k, v in mine.items() if v},
        Context(index=index, language=LANGUAGES[".py"], names=names),
    )

    assert all(edge.type is EdgeType.CALLS for edge in produced.edges)
    return (
        [(edge.source, edge.target) for edge in produced.edges],
        produced.counters["unresolved_calls"],
    )


def fn(name: str, parent: str | None = None, line: int = 1) -> Defines:
    return Defines(kind="function", name=name, parent=parent, line=line)


def test_a_function_in_the_same_file_becomes_an_edge() -> None:
    edges, unresolved = produce(
        {
            APP: [
                fn("save", line=1),
                fn("export", line=3),
                Calls(caller="export", callee="save", line=4),
            ]
        }
    )

    assert edges == [("function:src/app.py::export", "function:src/app.py::save")]
    assert unresolved == 0


def test_an_imported_function_crosses_the_file_boundary() -> None:
    edges, _ = produce(
        {
            APP: [
                Import(module="src", level=0, name="lib", alias=None, line=1),
                fn("build", line=3),
                Calls(caller="build", callee="lib.save", line=4),
            ],
            LIB: [fn("save")],
        }
    )

    assert edges == [("function:src/app.py::build", "function:src/lib.py::save")]


def test_the_lookup_starts_from_the_calling_function() -> None:
    """閉包呼叫外層函式裡的 helper——從 caller 那一層由內往外找（plan 5.5）。"""
    edges, _ = produce(
        {
            APP: [
                fn("build", line=1),
                fn("step", parent="build", line=2),
                fn("inner", parent="build", line=3),
                Calls(caller="build.inner", callee="step", line=4),
            ]
        }
    )

    assert edges == [
        ("function:src/app.py::build.inner", "function:src/app.py::build.step")
    ]


def test_self_lands_on_a_method_of_the_same_class() -> None:
    edges, _ = produce(
        {
            APP: [
                Defines(kind="class", name="Job", parent=None, line=1),
                fn("run", parent="Job", line=2),
                fn("step", parent="Job", line=4),
                Calls(caller="Job.run", callee="step", line=3, self_class="Job"),
            ]
        }
    )

    assert edges == [("function:src/app.py::Job.run", "function:src/app.py::Job.step")]


def test_calling_a_class_lands_on_its_constructor() -> None:
    edges, unresolved = produce(
        {
            APP: [
                Defines(kind="class", name="Job", parent=None, line=1),
                fn("__init__", parent="Job", line=2),
                Defines(kind="class", name="Plain", parent=None, line=4),
                fn("main", line=6),
                Calls(caller="main", callee="Job", line=7),
                Calls(caller="main", callee="Plain", line=8),
            ]
        }
    )

    # Plain 沒有 __init__，沒有函式節點可接
    assert edges == [("function:src/app.py::main", "function:src/app.py::Job.__init__")]
    assert unresolved == 1


def test_builtins_externals_and_unknown_receivers_produce_no_edge() -> None:
    edges, unresolved = produce(
        {
            APP: [
                Import(module="json", level=0, name=None, alias=None, line=1),
                fn("main", line=3),
                Calls(caller="main", callee="print", line=4),
                Calls(caller="main", callee="json.loads", line=5),
                Calls(caller="main", callee="value.step", line=6),
            ]
        }
    )

    assert edges == []
    assert unresolved == 3


def test_each_call_is_its_own_edge_with_its_own_line() -> None:
    produced = CallsProducer().produce(
        {
            APP: [
                Calls(caller="main", callee="save", line=3),
                Calls(caller="main", callee="save", line=4),
            ]
        },
        Context(
            index=from_files(["src/app.py"]),
            language=LANGUAGES[".py"],
            names=from_facts(
                {APP: [fn("save"), fn("main", line=2)]},
                from_files(["src/app.py"]),
                PythonResolver(),
            ),
        ),
    )

    assert [edge.properties for edge in produced.edges] == [
        {"callee": "save", "line": 3},
        {"callee": "save", "line": 4},
    ]


def test_the_counter_is_always_there_even_at_zero() -> None:
    _, unresolved = produce(
        {APP: [fn("main"), Calls(caller="main", callee="main", line=2)]}
    )

    assert unresolved == 0
