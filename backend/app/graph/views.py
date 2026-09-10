"""文件層級的視圖操作：篩邊、收合層級。

**都是同一張圖的查詢條件**，不是另一條管線。兩者有順序：`collapse()` 要靠
`contains` 與 `defines` 邊算層級，所以**先收合再篩邊**——反過來的話 imports
視圖裡沒有那兩種邊，就收不動了。

為什麼需要收合：檔案層有 83 個 `file` 節點、135 條聚合後的邊，而且
`app/models/__init__.py` 一個節點就吃掉 59 條入邊，畫面上是蜘蛛網中心。收到目
錄層之後剩 10 個目錄節點、63 條邊，最忙的節點只剩 7 條入邊——因為「所有檔案都
import models」在目錄層本來就該是**一條**邊。

刻意寫成 `GraphDocument → GraphDocument` 的純函式，不碰 networkx：只需要
`{nodes, edges}` 就算得出來，測試餵一份假文件即可，查詢層也不必為它長胖。
規則見 docs/backend/graph.md › 收合。
"""

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from app.models import Edge, EdgeType, GraphDocument, Node, NodeType, make_id

#: 外部套件在收合後怎麼呈現。收到目錄層時 ext 反而會變成節點的大宗（10 個目錄
#: 對 15 個套件），所以它需要自己的開關。
ExternalMode = Literal["full", "grouped", "hidden"]

#: `grouped` 時所有外部套件合併成的那一個節點
GROUPED_EXTERNAL_ID = make_id(NodeType.EXTERNAL_PACKAGE, "*")

#: 算層級時要爬的邊。**兩種都要吃**——`contains` 是檔案系統的包含、`defines`
#: 是程式碼的宣告包含，接起來才是完整的一棵樹。只認 `contains` 的話 class 與
#: function 上面沒有父節點，會被當成深度 0 的孤兒，每個層級都收不掉。
#: CLAUDE.md 圖模型那節把這件事寫成 `defines` 的代價。
_TREE_EDGES = frozenset({EdgeType.CONTAINS, EdgeType.DEFINES})


def collapse(
    document: GraphDocument,
    level: int | None = None,
    externals: ExternalMode = "full",
) -> GraphDocument:
    """把每個節點往上收到第 `level` 層；`None` 代表不收合。

    `level` 是層級樹（`contains` ＋ `defines`）上的深度：0 是 repo，1 是它的直
    接子項，依此類推。函式掛在檔案底下，所以比它所在的檔案深一層。
    **收不到那麼深的節點就保留自己**——根目錄下的 `README.md` 在 `level=2` 時
    上面沒有兩層目錄，維持原樣。
    """
    if level is None and externals == "full":
        return document

    target = _targets(document, level)
    target = _apply_external_mode(document, target, externals)

    nodes = _nodes(document, target, externals)
    edges = _edges(document, target)
    return GraphDocument(
        nodes=nodes,
        edges=edges,
        # cycles / 三個計數 / 分析時間講的是整份分析，不因為換個視圖而改變。
        meta=document.meta.model_copy(
            update={"node_count": len(nodes), "edge_count": len(edges)}
        ),
    )


def only_edges(
    document: GraphDocument, edge_types: Sequence[EdgeType]
) -> GraphDocument:
    """只保留這些型別的邊。**節點全部留著**，與 `CodeGraph.view()` 一致。

    篩掉的節點會讓人看不出它在整棵樹的哪個位置，而那正是這個工具要回答的事。
    """
    kept = [edge for edge in document.edges if edge.type in edge_types]
    return GraphDocument(
        nodes=document.nodes,
        edges=kept,
        meta=document.meta.model_copy(update={"edge_count": len(kept)}),
    )


def _targets(document: GraphDocument, level: int | None) -> dict[str, str]:
    """每個節點 id → 收合後代表它的節點 id。"""
    if level is None:
        return {node.id: node.id for node in document.nodes}

    parent = {
        edge.target: edge.source for edge in document.edges if edge.type in _TREE_EDGES
    }
    return {node.id: _ancestor(node.id, parent, level) for node in document.nodes}


def _ancestor(node_id: str, parent: Mapping[str, str], level: int) -> str:
    chain: list[str] = []
    current = node_id
    # 往上爬到頂。chain 是 [父, 祖父, …, repo]，長度就是這個節點的深度。
    while current in parent:
        current = parent[current]
        chain.append(current)

    depth = len(chain)
    if depth <= level:
        return node_id
    return chain[depth - level - 1]


def _apply_external_mode(
    document: GraphDocument, target: dict[str, str], externals: ExternalMode
) -> dict[str, str]:
    if externals == "full":
        return target

    for node in document.nodes:
        if node.type != NodeType.EXTERNAL_PACKAGE:
            continue
        # hidden 用空字串標記「這個節點不見了」，連帶讓碰到它的邊一起消失。
        target[node.id] = "" if externals == "hidden" else GROUPED_EXTERNAL_ID
    return target


def _nodes(
    document: GraphDocument, target: Mapping[str, str], externals: ExternalMode
) -> list[Node]:
    kept: dict[str, Node] = {}
    #: 收合後落在同一個節點裡的 imports，數量記在該節點上，不當成邊丟掉
    internal: dict[str, int] = {}
    packages: list[str] = []

    for node in document.nodes:
        destination = target[node.id]
        if not destination:
            continue
        if destination == GROUPED_EXTERNAL_ID:
            packages.append(node.label)
            continue
        if destination == node.id:
            kept[node.id] = node

    for edge in document.edges:
        if edge.type != EdgeType.IMPORTS:
            continue
        source, target_id = target[edge.source], target[edge.target]
        if source and source == target_id:
            internal[source] = internal.get(source, 0) + 1

    nodes = [_with_internal(node, internal.get(node.id, 0)) for node in kept.values()]
    if packages:
        nodes.append(_grouped_external(packages))
    return nodes


def _with_internal(node: Node, count: int) -> Node:
    """收合掉的內部 import 記在節點上——那代表「這個模組內部有多緊」，是資訊。"""
    if count == 0:
        return node
    return node.model_copy(
        update={"properties": {**node.properties, "internal_imports": count}}
    )


def _grouped_external(packages: Sequence[str]) -> Node:
    return Node(
        id=GROUPED_EXTERNAL_ID,
        type=NodeType.EXTERNAL_PACKAGE,
        label=f"外部套件 ({len(packages)})",
        # 名單留著，之後要做「點開展開」時不必重新分析
        properties={"packages": sorted(packages)},
    )


def _edges(document: GraphDocument, target: Mapping[str, str]) -> list[Edge]:
    """重新指向收合後的節點，去掉自環，平行的合成一條帶 `weight` 的邊。

    `imports` 的邊另外把被合併掉的原始邊留在 `properties["sources"]`，前端才
    問得出「這條 16 是哪幾個檔案造成的」。
    """
    merged: dict[tuple[str, str, EdgeType], Edge] = {}

    for edge in document.edges:
        source, destination = target[edge.source], target[edge.target]
        # 空字串＝那一端被藏起來了；相同＝收合後變成自環，都不畫
        if not source or not destination or source == destination:
            continue

        key = (source, destination, edge.type)
        existing = merged.get(key)
        if existing is None:
            merged[key] = Edge(
                source=source,
                target=destination,
                type=edge.type,
                properties=_collapsed_properties(edge),
            )
            continue
        existing.properties["weight"] += 1
        if edge.type == EdgeType.IMPORTS:
            existing.properties["sources"].append(_source_of(edge))

    return list(merged.values())


def _collapsed_properties(edge: Edge) -> dict[str, Any]:
    """收合後的邊帶什麼。

    層級邊（`contains`、`defines`）不帶 `sources`：它們被收掉的細節換一個層級
    就看得到，揹著只是讓 JSON 變大。`imports` 則相反——收合把「哪個檔案 import
    哪個檔案」整個吃掉了，不留下來就再也問不到。
    """
    if edge.type != EdgeType.IMPORTS:
        return {"weight": 1}
    return {"weight": 1, "sources": [_source_of(edge)]}


def _source_of(edge: Edge) -> dict[str, Any]:
    """被收合掉的那一筆原始 import，只留展示得到的欄位。"""
    return {
        "from": edge.source,
        "to": edge.target,
        "module": edge.properties.get("module"),
        "name": edge.properties.get("name"),
        "line": edge.properties.get("line"),
    }
