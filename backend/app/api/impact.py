"""影響範圍端點：點一個節點，改它會波及誰。

跟 `/api/analyze` 一樣無狀態——每次都重跑一次分析（本專案 0.05 秒）。分析結果存
哪、怎麼重用還沒決定（plan 4.4），決定之後這裡改成讀存好的圖，介面不變。

只做 HTTP 的事：算影響範圍是查詢層的 `CodeGraph.impact()`，換到畫面上的層級是
`views.project()`。規則見 docs/backend/api.md。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.analyze import graph_at
from app.graph import ExternalMode, UnknownNodeError, project
from app.models import GraphDocument

router = APIRouter()


class ImpactRequest(BaseModel):
    path: str
    #: 點的那個節點的 id——畫面上看得到的那一個，收合過的也可以
    node: str
    #: 跟 `/api/analyze` 同一組查詢條件，回傳的節點才會是畫面上已經有的那些
    level: int | None = None
    externals: ExternalMode = "full"


@router.post("/api/impact", response_model=GraphDocument)
def impact(request: ImpactRequest) -> GraphDocument:
    graph = graph_at(request.path)
    try:
        affected = graph.impact(request.node)
    except UnknownNodeError:
        raise HTTPException(status_code=404, detail="沒有這個節點") from None
    return project(
        affected, graph.document(), level=request.level, externals=request.externals
    )
