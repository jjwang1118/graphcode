# api.md

後端 HTTP 層的決定：路由放哪、怎麼註冊、路徑怎麼命名。

只談 API。其餘後端主題各自獨立成檔。

---

## 位置

| 要素 | 放哪 | 理由 |
|---|---|---|
| **路由定義** — `@router.get(...)` 與 handler | `app/api/<主題>.py` | `app/api/` 就是 HTTP 層 |
| **路由註冊** — `include_router` | `app/main.py` | 註冊是接線，接線是進入點的職責 |
| **request / response 形狀** | 與該路由同檔，或 `app/models/` | 若是圖本身的形狀（`{ nodes, edges, meta }`）一律用 `app/models/`，不另定 |

一個主題一個檔（`health.py`、日後的 `analyze.py`、`graphs.py`），檔內以 `APIRouter` 收攏。

**路由定義與註冊分開，不是分層儀式** — 分開之後，各 API 模組彼此不需要知道對方存在，新增一個不會動到既有的任何一個。

---

## 註冊方式：逐一註冊

每個模組在 `app/main.py` 明確註冊，**不做自動掃描、不設聚合層**。

```python
# app/main.py
from fastapi import FastAPI

from app.api import health

app = FastAPI(title="codegraph")
app.include_router(health.router)
```

新增一個模組 = `main.py` 動兩行（import 一個名字、`include_router` 一行）。


---

## 路徑前綴

`/api` 由**各模組自行寫在路徑裡**：

```python
@router.get("/api/ping")
```

不在 `APIRouter(prefix="/api")` 或聚合層統一加。

| | |
|---|---|
| 代價 | 每個路由都要重複寫 `/api`；日後版本化成 `/api/v1` 得逐檔改 |
| 理由 | 目前只有一個模組，統一前綴的機制此刻只是預留。真要版本化時，那次改動本來就會一併引入聚合層 |

前端的 vite proxy 以 `/api` 為條件轉發到 `:8000`，所以**這個前綴是前後端的約定，不能隨意更動**。

---

## 現有端點

| 方法 | 路徑 | 回傳 | 定義在 |
|---|---|---|---|
| `GET` | `/api/ping` | `{"status": "ok"}` | `app/api/health.py` |
| `POST` | `/api/analyze` | `GraphDocument` | `app/api/analyze.py` |

---

## `POST /api/analyze`

```json
{ "path": "/home/user/project", "edge_types": ["contains"] }
```

| 欄位 | 說明 |
|---|---|
| `path` | 本機路徑，必須落在 allowlist 內（見 `ingest.md`） |
| `edge_types` | 省略＝整張圖；給了就只保留這些型別的邊 |

一次走完 ingest → scan → parse → resolve → build → 查詢層，同步回傳整份 `GraphDocument`。

### 管線編排不在這一層

端點只做兩件事：**把請求換成一個安全的根目錄**（呼叫 ingest）、**把管線的例外換成狀態碼**。中間那條管線在 `app/pipeline.py`。

| | |
|---|---|
| 為什麼分開 | API 層不該知道管線有幾段。管線多一段（parse、resolve）不該讓 HTTP 層跟著改 |
| 換到什麼 | `analyze(root) -> CodeGraph` 是純函式，不啟動 FastAPI 就能測——目前 httpx 未安裝、`TestClient` 用不了，這一點特別實際 |

`pipeline.py` 唯一偏離「單向管線」的地方：scan 產出的節點會等 parse 跑完才交給 build，因為解析失敗的訊息要貼回對應的 `file` 節點（`properties["parse_error"]`）。不讓 build 做這件事，是因為 build 的定位是「不在乎節點從哪來」。

### 為什麼是 POST

它不建立資料，所以 `GET` 也說得通。選 `POST` 的理由是另外三個：

| 理由 | 說明 |
|---|---|
| 不想被快取 | `GET` 可被瀏覽器與中間層快取。程式碼改了重新分析，可能拿到舊的圖 |
| 路徑不進網址 | 網址會被記進存取日誌、瀏覽器歷史與 referrer。使用者的絕對路徑不該到處留副本 |
| 參數會長大 | body 是一個 pydantic model，加欄位就是加一行；query string 的陣列參數寫法彆扭 |

### 視圖就是一個欄位

前端切換「目錄樹 / 依賴圖」改的是 `edge_types`，**不是換一個端點**。這是「視圖 = 同一張圖的查詢條件」在 API 上的樣子。

### `response_model` 一定要宣告

```python
@router.post("/api/analyze", response_model=GraphDocument)
```

不宣告也能動、回傳的 JSON 也一樣，但 `/openapi.json` 裡就**不會有這個型別**，日後想從它生成前端的 `types.ts` 會什麼都生不出來。而且這個疏漏不報錯，很難發現。

---

## 錯誤

| 狀況 | 狀態碼 | 回給前端 |
|---|---|---|
| 路徑不在 allowlist 內、不存在、不是目錄 | `400` | `路徑不被允許` |
| 組圖失敗（`BuildError`） | `500` | `分析失敗` |

`BuildError` 是**管線自己產出了不一致的圖**，不是使用者給錯東西，所以是 500 而不是 400。

**詳細原因只寫進日誌。** 回「`/etc` 不在允許清單 `/home/user/project` 內」等於把 allowlist 內容與目錄結構送出去，試幾次就能把伺服器的檔案系統摸清楚。所以四種被拒絕的情況共用同一句話。

---

## 未定之處

| 項目 | 缺什麼 |
|---|---|
| 大型 repo 的回應 | 目前同步、一次回全部。上萬檔案時可能撐爆瀏覽器或逾時，屆時才需要工作 id 與輪詢 |
| 存檔相關端點 | `store.save()` / `load()` 目前只是函式，沒有對應端點；要不要開、`data/` 放哪都未定 |
| 前端的請求型別 | `types.ts` 目前只有回應那半，沒有 `AnalyzeRequest`。等寫 `client.ts` 時補 |
