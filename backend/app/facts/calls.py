"""呼叫事實 → `calls` 邊。

跟 `inherits.py` 同一個形狀：要查的是**名字**（`foo()` 的 `foo`），查表的演算法
在 `app/resolve/names.py`，這裡只負責把查到的結果接成邊。

======================  =============================================
``foo()``               從呼叫所在的函式由內往外查 foo
``mod.foo()``           本檔 import 的 mod 裡的 foo
``self.foo()``          方法所屬 class 的 foo（parse 已記下是哪個 class）
``Runner()``            Runner 有 ``__init__`` 就接到它
======================  =============================================

**只連專案內的函式。** 查不到（builtin、外部套件、`變數.foo()`）就不產生邊，
計進 `unresolved_calls`——跟 `unresolved_inherits` 同一套處置（plan 5.7 先採
「只畫解得出來的」）。規則見 docs/backend/facts.md。
"""

from collections.abc import Mapping, Sequence

from app.facts.declarations import path_of
from app.facts.production import Context, Production
from app.models import Edge, EdgeType, NodeType, make_id
from app.parsers import Calls
from app.resolve import Declaration, NameIndex


class CallsProducer:
    def produce(
        self, facts: Mapping[str, Sequence[Calls]], context: Context
    ) -> Production:
        edges: list[Edge] = []
        unresolved = 0

        for file_id in sorted(facts):
            for fact in facts[file_id]:
                found = _target(context.names, file_id, fact)
                if found is None:
                    unresolved += 1
                    continue
                edges.append(_edge(file_id, fact, found))

        return Production(edges=tuple(edges), counters={"unresolved_calls": unresolved})


def _target(names: NameIndex, file_id: str, fact: Calls) -> Declaration | None:
    """被呼叫的是哪個**函式**；不是函式的回 None。"""
    if fact.self_class is not None:
        # 完整路徑直接查，不必由內往外——`Job.run` 就是 `Job.run`
        found = names.lookup(file_id, f"{fact.self_class}.{fact.callee}")
    else:
        found = names.lookup(file_id, fact.callee, fact.caller)

    if found is not None and found.kind == "class":
        # 呼叫 class 就是建構它，實際跑的是 __init__。沒寫 __init__ 的 class 沒
        # 有函式節點可接
        found = names.lookup(found.file, f"{found.qualified}.__init__")
    return found if found is not None and found.kind == "function" else None


def _edge(file_id: str, fact: Calls, found: Declaration) -> Edge:
    """來源是呼叫所在的函式，目標是查到的那個函式。

    兩端都是 `DeclarationProducer` 從**同一批 `Defines` 事實**產出的節點，所以
    不會指向不存在的節點（`graph.md` B2 會擋）。
    """
    return Edge(
        source=make_id(NodeType.FUNCTION, path_of(file_id), member=fact.caller),
        target=make_id(NodeType.FUNCTION, path_of(found.file), member=found.qualified),
        type=EdgeType.CALLS,
        # `callee` 是原始碼寫的樣子，跟 target 的 id 不一樣——接對了沒有，看這兩
        # 個就知道。一次呼叫一條邊，行號各自保留（同 resolve.md R16）
        properties={"callee": fact.callee, "line": fact.line},
    )
