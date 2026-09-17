"""繼承事實 → `inherits` 邊。

`Defines` 自己就是節點、`Import` 要查模組名，`Inherits` 介於兩者之間：它要查的
是**名字**（`class Foo(Bar)` 的 `Bar`），查表的演算法在 `app/resolve/names.py`，
這裡只負責把查到的結果接成邊。

**只連專案內的 class。** 查不到就不產生邊，計進 `unresolved_inherits`：

===============================  ================================
``class Runner(Base)``           Base 是本檔或 import 進來的 class → 邊
``class Error(Exception)``       builtin → 沒有邊
``class Request(BaseModel)``     外部套件 → 沒有邊
===============================  ================================

不把外部的那些接到 `ext:` 節點，是為了讓 `inherits` 嚴格維持 CLAUDE.md 圖模型
寫的 **class → class**。代價是外部繼承在圖上看不見，數字留在 `meta`。規則見
docs/backend/facts.md。
"""

from collections.abc import Mapping, Sequence

from app.facts.declarations import NODE_TYPE, path_of
from app.facts.production import Context, Production
from app.models import Edge, EdgeType, NodeType, make_id
from app.parsers import Inherits
from app.resolve import Declaration


class InheritsProducer:
    def produce(
        self, facts: Mapping[str, Sequence[Inherits]], context: Context
    ) -> Production:
        edges: list[Edge] = []
        unresolved = 0

        for file_id in sorted(facts):
            for fact in facts[file_id]:
                found = context.names.lookup(file_id, fact.base)
                if found is None or found.kind != "class":
                    # 查不到，或查到的是同名的函式——繼承只能是 class → class
                    unresolved += 1
                    continue
                edges.append(_edge(file_id, fact, found))

        return Production(
            edges=tuple(edges), counters={"unresolved_inherits": unresolved}
        )


def _edge(file_id: str, fact: Inherits, found: Declaration) -> Edge:
    """來源是子類別的節點，目標是查到的那個宣告。

    兩端都是 `DeclarationProducer` 從**同一批 `Defines` 事實**產出來的節點，所
    以不會指向不存在的節點（`graph.md` B2 會擋）。
    """
    return Edge(
        source=make_id(NodeType.CLASS, path_of(file_id), member=fact.child),
        target=make_id(
            NODE_TYPE[found.kind], path_of(found.file), member=found.qualified
        ),
        type=EdgeType.INHERITS,
        # `base` 是原始碼寫的樣子（`nx.Graph`），跟 target 的 id 不一樣——接對了
        # 沒有，看這兩個就知道。
        properties={"base": fact.base, "line": fact.line},
    )
