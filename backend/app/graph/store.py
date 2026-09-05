"""JSON 存檔與讀回。

讀回時走的是同一個 `build()`，所以讀取路徑與分析路徑共用同一套驗證與 meta
計算。檔案存在哪、檔名怎麼取由呼叫端決定。規則見 docs/backend/graph.md。
"""

from pathlib import Path

from app.graph.build import Diagnostics, build
from app.graph.query import CodeGraph
from app.models import GraphDocument


def save(graph: CodeGraph, path: Path) -> None:
    path.write_text(graph.document().model_dump_json(indent=2), encoding="utf-8")


def load(path: Path) -> CodeGraph:
    """讀回並重新建圖；檔案裡的圖若不合法，這裡就會擋下來。"""
    document = GraphDocument.model_validate_json(path.read_text(encoding="utf-8"))
    # 計數跟分析時間一樣是「當時算出來的」，重建時要帶回去，否則讀檔會歸零。
    return build(
        document.nodes,
        document.edges,
        analyzed_at=document.meta.analyzed_at,
        diagnostics=Diagnostics(
            parse_failures=document.meta.parse_failures,
            ambiguous_imports=document.meta.ambiguous_imports,
            unresolved_imports=document.meta.unresolved_imports,
        ),
    )
