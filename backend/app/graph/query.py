"""查詢層介面：外界碰得到圖的唯一入口。

networkx 物件不外露，方法一律回 `app/models/` 的型別 —— 破了這條，日後換
Neo4j / Kuzu 的抽象就是裝飾品。規則見 docs/backend/graph.md。
"""

from collections import deque

import networkx as nx  # type: ignore[import-untyped]

from app.graph.views import TREE_EDGES
from app.models import Edge, EdgeType, GraphDocument, Meta, Node


class UnknownNodeError(KeyError):
    """問了一個圖裡沒有的節點。"""


class CodeGraph:
    def __init__(self, graph: nx.MultiDiGraph, meta: Meta) -> None:
        self._graph = graph
        self.meta = meta

    def document(self) -> GraphDocument:
        """整張圖。"""
        return self.view()

    def view(self, *edge_types: EdgeType) -> GraphDocument:
        """只保留指定型別的邊；不指定就是整張圖。

        節點一律全部保留 —— 「這個檔案存在但沒有人 import 它」本身就是資訊。
        """
        nodes = self._nodes()
        edges = [
            edge for edge in self._edges() if not edge_types or edge.type in edge_types
        ]
        return GraphDocument(
            nodes=nodes, edges=edges, meta=self._meta_for(nodes, edges)
        )

    def impact(self, node_id: str) -> GraphDocument:
        """改 `node_id` 會波及誰：沿 `calls` **反向**一路往上找所有呼叫者。

        起點是這個節點**加上它在層級樹底下的全部後代**——點一個檔案，等於問
        「這個檔案裡任何一個函式被改了」。每個節點的 `properties["impact_depth"]`
        是它離起點幾步（起點為 0），前端依這個數字一層一層亮起來。

        回傳的邊只有**往外擴散的那一步**（呼叫者比被呼叫者深一層），同一層之
        間互相呼叫的不算——那條線不是波及的路徑。
        """
        if node_id not in self._graph:
            raise UnknownNodeError(node_id)

        depth = {seed: 0 for seed in self._descendants(node_id)}
        queue = deque(depth)
        while queue:
            callee = queue.popleft()
            for caller, _, data in self._graph.in_edges(callee, data=True):
                if data["edge"].type is EdgeType.CALLS and caller not in depth:
                    depth[caller] = depth[callee] + 1
                    queue.append(caller)

        nodes = [
            self._graph.nodes[node]["node"].model_copy(
                update={
                    "properties": {
                        **self._graph.nodes[node]["node"].properties,
                        "impact_depth": steps,
                    }
                }
            )
            for node, steps in depth.items()
        ]
        edges = [
            edge
            for edge in self._edges()
            if edge.type is EdgeType.CALLS
            and edge.source in depth
            and edge.target in depth
            and depth[edge.source] == depth[edge.target] + 1
        ]
        return GraphDocument(
            nodes=nodes, edges=edges, meta=self._meta_for(nodes, edges)
        )

    def _descendants(self, node_id: str) -> list[str]:
        """自己 ＋ 層級樹（`contains` ＋ `defines`）底下的全部後代，前序。"""
        found = [node_id]
        stack = [node_id]
        while stack:
            current = stack.pop()
            for _, child, data in self._graph.out_edges(current, data=True):
                if data["edge"].type in TREE_EDGES:
                    found.append(child)
                    stack.append(child)
        return found

    def _nodes(self) -> list[Node]:
        return [data["node"] for _, data in self._graph.nodes(data=True)]

    def _edges(self) -> list[Edge]:
        return [data["edge"] for _, _, data in self._graph.edges(data=True)]

    def _meta_for(self, nodes: list[Node], edges: list[Edge]) -> Meta:
        # 數量隨視圖走，其餘沿用：cycles 與 analyzed_at 是整份分析的結論。
        return self.meta.model_copy(
            update={"node_count": len(nodes), "edge_count": len(edges)}
        )
