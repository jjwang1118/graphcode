"""把事實接成 `imports` 邊，並造出對不到的 `external_package` 節點。

一筆 fact 一條邊——`from app.ingest import A, B, C` 是三條平行邊。圖用
`MultiDiGraph` 就是為了這個；**邊的聚合是視圖層的事，不該在資料層先做掉**。
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.models import Edge, EdgeType, Node, NodeType
from app.models.ids import PREFIX
from app.parsers import Fact
from app.resolve.index import ModuleIndex, Resolution


class Resolver(Protocol):
    def target(
        self, fact: Fact, importer_id: str, index: ModuleIndex
    ) -> Resolution | None: ...


@dataclass(frozen=True)
class ResolveResult:
    """`imports` 那一半的圖，加上兩個「這張圖有多少成分是猜的」的指標。

    準確度本身沒辦法自動驗證（沒有標準答案可比對），這兩個數字是唯一拿得到的
    間接指標。
    """

    nodes: tuple[Node, ...] = ()
    edges: tuple[Edge, ...] = ()
    #: 相對 import 爬出專案外，沒有產生邊的筆數
    unresolved: int = 0
    #: 同一個模組名對到多個檔案，挑了一個的筆數
    ambiguous: int = 0


def to_edges(
    facts: Mapping[str, Sequence[Fact]],
    index: ModuleIndex,
    resolver: Resolver,
) -> ResolveResult:
    """`facts` 以來源檔案的節點 id 為 key——fact 自己不知道它從哪個檔案來。"""
    edges: list[Edge] = []
    externals: dict[str, Node] = {}
    unresolved = 0
    ambiguous = 0

    for importer_id in sorted(facts):
        for fact in facts[importer_id]:
            found = resolver.target(fact, importer_id, index)
            if found is None:
                unresolved += 1
                continue
            if found.ambiguous:
                ambiguous += 1
            edges.append(_edge(importer_id, fact, found))

    for edge in edges:
        node = _external(edge.target)
        if node is not None:
            externals.setdefault(node.id, node)

    return ResolveResult(
        nodes=tuple(externals[node_id] for node_id in sorted(externals)),
        edges=tuple(edges),
        unresolved=unresolved,
        ambiguous=ambiguous,
    )


def _edge(importer_id: str, fact: Fact, found: Resolution) -> Edge:
    properties: dict[str, Any] = {"module": _written(fact), "line": fact.line}
    if fact.name is not None:
        properties["name"] = fact.name
    if found.ambiguous:
        properties["ambiguous"] = list(found.ambiguous)

    return Edge(
        source=importer_id,
        target=found.target,
        type=EdgeType.IMPORTS,
        properties=properties,
    )


def _written(fact: Fact) -> str:
    """原始碼裡寫的那個模組字串，`from ..pkg import x` 就是 `..pkg`。"""
    return "." * fact.level + (fact.module or "")


def _external(node_id: str) -> Node | None:
    prefix, _, name = node_id.partition(":")
    if prefix != PREFIX[NodeType.EXTERNAL_PACKAGE]:
        return None
    return Node(id=node_id, type=NodeType.EXTERNAL_PACKAGE, label=name)
