"""組圖與驗證。

不在乎節點與邊從哪來：分析路徑吃 scan（日後加 resolve）的輸出，讀取路徑吃
JSON 反序列化的結果，兩者共用這一段。規則見 docs/backend/graph.md。
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import networkx as nx  # type: ignore[import-untyped]

from app.graph.errors import BuildError
from app.graph.query import CodeGraph
from app.models import Edge, EdgeType, Meta, Node


@dataclass(frozen=True)
class Diagnostics:
    """分析過程的問題計數。

    build 只是把它抄進 `meta`——它不認識 parse 與 resolve，也不該認識。數字由
    產生問題的那一層自己算，見 docs/backend/parse.md 與 resolve.md。
    """

    parse_failures: int = 0
    ambiguous_imports: int = 0
    unresolved_imports: int = 0


def build(
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    analyzed_at: datetime | None = None,
    diagnostics: Diagnostics | None = None,
) -> CodeGraph:
    """驗證並組出圖；有問題時丟 `BuildError`。

    `analyzed_at` 預設是現在。讀取路徑（`store.load()`）會把檔案裡原本的分析
    時間傳進來，否則讀檔會被誤記成一次新的分析。
    """
    _reject_duplicate_ids(nodes)
    _reject_dangling_edges(nodes, edges)

    graph = nx.MultiDiGraph()
    for node in nodes:
        graph.add_node(node.id, node=node)
    for edge in edges:
        graph.add_edge(edge.source, edge.target, type=edge.type, edge=edge)

    return CodeGraph(graph, _meta(graph, nodes, edges, analyzed_at, diagnostics))


def _reject_duplicate_ids(nodes: Sequence[Node]) -> None:
    duplicates = sorted(
        node_id
        for node_id, count in Counter(node.id for node in nodes).items()
        if count > 1
    )
    if duplicates:
        raise BuildError(f"節點 id 重複：{', '.join(duplicates)}")


def _reject_dangling_edges(nodes: Sequence[Node], edges: Sequence[Edge]) -> None:
    known = {node.id for node in nodes}
    # 一次列出所有壞邊：這類錯誤通常整批出現。
    dangling = sorted(
        f"{edge.source} -> {edge.target}"
        for edge in edges
        if edge.source not in known or edge.target not in known
    )
    if dangling:
        raise BuildError(f"邊指向不存在的節點：{', '.join(dangling)}")


def _meta(
    graph: nx.MultiDiGraph,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    analyzed_at: datetime | None,
    diagnostics: Diagnostics | None,
) -> Meta:
    counts = diagnostics or Diagnostics()
    return Meta(
        node_count=len(nodes),
        edge_count=len(edges),
        cycles=_import_cycles(graph),
        # 「孤立」的定義（哪些型別算、看哪種邊）還沒定，見 docs/backend/graph.md。
        isolated_nodes=[],
        parse_failures=counts.parse_failures,
        ambiguous_imports=counts.ambiguous_imports,
        unresolved_imports=counts.unresolved_imports,
        analyzed_at=analyzed_at or datetime.now(UTC),
    )


def _import_cycles(graph: nx.MultiDiGraph) -> list[list[str]]:
    imports = nx.DiGraph()
    imports.add_nodes_from(graph.nodes)
    imports.add_edges_from(
        (source, target)
        for source, target, edge_type in graph.edges(data="type")
        if edge_type == EdgeType.IMPORTS
    )
    return sorted(_canonical(cycle) for cycle in nx.simple_cycles(imports))


def _canonical(cycle: list[str]) -> list[str]:
    """旋轉成從 id 最小的節點開始 —— 起點是任意的，不固定就無法重現。"""
    start = cycle.index(min(cycle))
    return cycle[start:] + cycle[:start]
