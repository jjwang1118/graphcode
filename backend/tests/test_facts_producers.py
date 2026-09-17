"""查表分派（F1–F5）。

最重要的一條是 `test_a_brand_new_fact_type_needs_no_change_outside_the_table`
——plan 5.2 的完成條件「加一種 Fact 不必在 build 加一個 `if`」就是它。
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pytest

from app.facts import Context, Producer, Production, UnknownFactError, to_graph
from app.languages import LANGUAGES
from app.models import Edge, EdgeType, Node, NodeType
from app.parsers import Defines, Fact, Import
from app.resolve import NameIndex, from_files

FILE = "file:main.py"


@pytest.fixture
def context() -> Context:
    return Context(
        index=from_files(["main.py", "pkg/helper.py"]),
        language=LANGUAGES[".py"],
        names=NameIndex(declared={}, imported={}),
    )


# --- 一種全新的 Fact，只動表 ---------------------------------------------------


@dataclass(frozen=True)
class Mentions:
    """測試自己發明的 Fact 型別。`app/` 底下沒有任何地方認識它。"""

    name: str


class MentionProducer:
    def produce(
        self, facts: Mapping[str, Sequence[Mentions]], context: Context
    ) -> Production:
        return Production(
            nodes=(
                Node(id="ext:mentioned", type=NodeType.EXTERNAL_PACKAGE, label="x"),
            ),
            edges=tuple(
                Edge(source=file_id, target="ext:mentioned", type=EdgeType.IMPORTS)
                for file_id in facts
            ),
            counters={"unresolved_imports": 1},
        )


def test_a_brand_new_fact_type_needs_no_change_outside_the_table(
    context: Context,
) -> None:
    produced = to_graph(
        {FILE: [Mentions(name="x")]},
        context,
        producers={Mentions: MentionProducer()},
    )

    assert [node.id for node in produced.nodes] == ["ext:mentioned"]
    assert [(edge.source, edge.target) for edge in produced.edges] == [
        (FILE, "ext:mentioned")
    ]
    assert produced.counters == {"unresolved_imports": 1}


def test_a_fact_nobody_handles_is_loud(context: Context) -> None:
    # 副檔名查不到 parser 是正常的；事實沒有產生器不是，那是表漏了一筆。
    with pytest.raises(UnknownFactError, match="Mentions"):
        to_graph({FILE: [Mentions(name="x")]}, context, producers={})


# --- 分堆 ---------------------------------------------------------------------


def test_each_producer_only_sees_its_own_kind(context: Context) -> None:
    seen: dict[type, list[Fact]] = {}

    class Recording:
        def __init__(self, kind: type) -> None:
            self.kind = kind

        def produce(
            self, facts: Mapping[str, Sequence[Fact]], context: Context
        ) -> Production:
            seen[self.kind] = [fact for items in facts.values() for fact in items]
            return Production()

    declared = Defines(kind="function", name="run", parent=None, line=2)
    imported = Import(module="os", level=0, name=None, alias=None, line=1)
    producers: dict[type, Producer] = {
        Defines: Recording(Defines),
        Import: Recording(Import),
    }

    to_graph({FILE: [imported, declared]}, context, producers=producers)

    assert seen == {Defines: [declared], Import: [imported]}


def test_nothing_in_nothing_out(context: Context) -> None:
    assert to_graph({}, context) == Production()


# --- 預設那張表 ---------------------------------------------------------------


def test_the_default_table_sends_each_kind_down_its_own_path(context: Context) -> None:
    produced = to_graph(
        {
            FILE: [
                Import(module="pkg.helper", level=0, name=None, alias=None, line=1),
                Import(module="requests", level=0, name=None, alias=None, line=2),
                Defines(kind="class", name="Runner", parent=None, line=4),
            ]
        },
        context,
    )

    # 宣告直接變節點；import 一條接到專案內的檔案、一條造出外部套件節點
    assert [node.id for node in produced.nodes] == [
        "class:main.py::Runner",
        "ext:requests",
    ]
    assert [(edge.source, edge.target, edge.type) for edge in produced.edges] == [
        (FILE, "class:main.py::Runner", EdgeType.DEFINES),
        (FILE, "file:pkg/helper.py", EdgeType.IMPORTS),
        (FILE, "ext:requests", EdgeType.IMPORTS),
    ]


def test_the_counters_are_named_after_the_diagnostics_fields(context: Context) -> None:
    # 爬出專案外，解不掉
    produced = to_graph(
        {FILE: [Import(module=None, level=3, name="x", alias=None, line=1)]},
        context,
    )

    assert produced.counters == {"ambiguous_imports": 0, "unresolved_imports": 1}
