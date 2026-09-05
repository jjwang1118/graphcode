"""分析端點：本機路徑 → 圖。

只做 HTTP 的事：把請求換成一個安全的根目錄、把管線的例外換成狀態碼。管線本身
在 `app/pipeline.py`，這一層不知道它有幾段。規則見 docs/backend/api.md。
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.graph import BuildError
from app.ingest import IngestError, allowed_roots_from_env, from_local_path
from app.models import EdgeType, GraphDocument
from app.pipeline import analyze as run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter()


class AnalyzeRequest(BaseModel):
    path: str
    #: 省略就是整張圖；給了就只保留這些型別的邊。
    edge_types: list[EdgeType] | None = None


@router.post("/api/analyze", response_model=GraphDocument)
def analyze(request: AnalyzeRequest) -> GraphDocument:
    try:
        root = from_local_path(request.path, allowed_roots_from_env())
    except IngestError:
        # 詳細原因只進日誌：回給前端等於洩漏允許清單與目錄結構。
        logger.warning("路徑被拒絕", exc_info=True)
        raise HTTPException(status_code=400, detail="路徑不被允許") from None

    try:
        graph = run_pipeline(root)
    except BuildError:
        # 走到這裡是管線自己產出了不一致的圖，不是使用者的錯。
        logger.exception("組圖失敗")
        raise HTTPException(status_code=500, detail="分析失敗") from None

    if request.edge_types:
        return graph.view(*request.edge_types)
    return graph.document()
