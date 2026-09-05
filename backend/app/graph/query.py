"""查詢層介面：外界碰得到圖的唯一入口。

networkx 物件不外露，方法一律回 `app/models/` 的型別 —— 破了這條，日後換
Neo4j / Kuzu 的抽象就是裝飾品。規則見 docs/backend/graph.md。
"""

import networkx as nx  # type: ignore[import-untyped]

from app.models import Edge, EdgeType, GraphDocument, Meta, Node


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

    def _nodes(self) -> list[Node]:
        return [data["node"] for _, data in self._graph.nodes(data=True)]

    def _edges(self) -> list[Edge]:
        return [data["edge"] for _, _, data in self._graph.edges(data=True)]

    def _meta_for(self, nodes: list[Node], edges: list[Edge]) -> Meta:
        # 數量隨視圖走，其餘沿用：cycles 與 analyzed_at 是整份分析的結論。
        return self.meta.model_copy(
            update={"node_count": len(nodes), "edge_count": len(edges)}
        )
