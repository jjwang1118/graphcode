"""序列化契約：跨越邊界的那份圖資料。

只描述形狀，不認識任何生產者。「每條邊的兩端節點都存在」由 build 驗證。
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.types import EdgeType, NodeType


class Node(BaseModel):
    id: str
    type: NodeType
    label: str
    properties: dict[str, Any] = Field(default_factory=dict)


class Edge(BaseModel):
    source: str
    target: str
    type: EdgeType
    properties: dict[str, Any] = Field(default_factory=dict)


class Meta(BaseModel):
    """build 算出來的衍生資訊，整張圖一份。"""

    node_count: int = 0
    edge_count: int = 0
    cycles: list[list[str]] = Field(default_factory=list)
    isolated_nodes: list[str] = Field(default_factory=list)
    #: 解析失敗的檔案數。哪幾個看 file 節點的 `properties["parse_error"]`
    parse_failures: int = 0
    #: 從多個候選裡挑出來的 imports 邊數。哪幾條看邊的 `properties["ambiguous"]`
    ambiguous_imports: int = 0
    #: 爬出專案外、沒有產生邊的相對 import 筆數
    unresolved_imports: int = 0
    analyzed_at: datetime | None = None


class GraphDocument(BaseModel):
    """磁碟儲存格式與 API 回傳格式，兩者形狀相同、內容不同。"""

    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    meta: Meta = Field(default_factory=Meta)
