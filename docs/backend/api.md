# api 規格

對應程式碼 `backend/app/api/`（管線編排在 `backend/app/pipeline.py`）。

---

## 1. 職責

HTTP 層。**只做 HTTP 的事。**

| 做 | 不做 |
|---|---|
| 解析請求、驗證形狀 | 編排管線（`pipeline.py` 的事） |
| 把請求換成一個安全的根目錄（呼叫 ingest） | 知道管線有幾段 |
| 把管線的例外換成狀態碼 | 產生節點與邊 |
| 依請求套用查詢條件 | 算收合與篩邊的內容（`app/graph/views.py` 的事） |

---

## 2. 介面

### 2.1 端點

| 方法 | 路徑 | 回傳 | 定義在 |
|---|---|---|---|
| `GET` | `/api/ping` | `{"status": "ok"}` | `app/api/health.py` |
| `POST` | `/api/analyze` | `GraphDocument` | `app/api/analyze.py` |

### 2.2 `AnalyzeRequest`

| 欄位 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `path` | `str` | 必填 | 本機路徑，必須落在 allowlist 內（見 `ingest.md`） |
| `edge_types` | `list[EdgeType] \| None` | `None` | 省略＝整張圖；給了就只保留這些型別的邊 |
| `level` | `int \| None` | `None` | 收合到**層級樹**（`contains` ＋ `defines`）的第幾層（0＝repo）；省略＝不收合。函式比它所在的檔案深一層 |
| `externals` | `ExternalMode` | `"full"` | `full` / `grouped` / `hidden`，見 `graph.md` §3.5 |

```json
{ "path": "/home/user/project", "level": 3, "externals": "grouped" }
```

後端的預設是「什麼都不做」（不收合、不篩邊、外部套件全畫）。**前端有自己的預設**（`level=3`、`externals="grouped"`），那是前端的選擇，不是後端的行為。

### 2.3 回應

一律是 `GraphDocument`（`{ nodes, edges, meta }`），形狀見 `graph_schema.md`。這份形狀同時是磁碟儲存格式，**前端只需要認識一種形狀**。

---

## 3. 行為

### 3.1 模組組織

| # | 規則 |
|---|---|
| A1 | 一個主題一個檔（`health.py`、`analyze.py`），檔內以 `APIRouter` 收攏。 |
| A2 | 路由**註冊**在 `app/main.py`，逐一 `include_router`，**不做自動掃描、不設聚合層**。 |
| A3 | `/api` 前綴由各模組**自行寫在路徑裡**，不用 `APIRouter(prefix=...)`。 |
| A4 | 每個路由都必須宣告 `response_model`。 |

新增一個模組 ＝ `main.py` 動兩行（import 一個名字、`include_router` 一行）。

A3 的代價與理由：

| | |
|---|---|
| 代價 | 每個路由都要重複寫 `/api`；日後版本化成 `/api/v1` 得逐檔改 |
| 理由 | 目前只有兩個模組，統一前綴的機制此刻只是預留。真要版本化時，那次改動本來就會一併引入聚合層 |

> 前端的 vite proxy 以 `/api` 為條件轉發到 `:8000`，所以**這個前綴是前後端的約定，不能隨意更動**。

### 3.2 `POST /api/analyze` 的流程

| # | 規則 |
|---|---|
| A5 | 先 `from_local_path(request.path, allowed_roots_from_env())` 取得根目錄。 |
| A6 | 再 `pipeline.analyze(root)` 走完管線，拿到 `CodeGraph`。 |
| A7 | 對 `graph.document()` 套用查詢條件，**順序固定：先 `collapse()` 再 `only_edges()`**。 |
| A8 | `edge_types` 為 `None` **或空陣列**時不篩邊。 |
| A9 | 同步回傳，一次回整份文件。 |

A7 的順序不可對調：`collapse()` 要靠 `contains` 邊算層級，先篩成 imports 視圖的話那些邊就沒了，收不動（見 `graph.md` §3.6）。

### 3.3 為什麼是 POST（A4 之外的決定）

它不建立資料，所以 `GET` 也說得通。選 `POST` 的理由是另外三個：

| 理由 | 說明 |
|---|---|
| 不想被快取 | `GET` 可被瀏覽器與中間層快取。程式碼改了重新分析，可能拿到舊的圖 |
| 路徑不進網址 | 網址會被記進存取日誌、瀏覽器歷史與 referrer。使用者的絕對路徑不該到處留副本 |
| 參數會長大 | body 是一個 pydantic model，加欄位就是加一行；query string 的陣列參數寫法彆扭 |

### 3.4 管線編排 · `pipeline.py`

`analyze(root: Path) -> CodeGraph`，不在 `app/api/` 之下。

| # | 規則 |
|---|---|
| P1 | 依序呼叫 `scan.from_root()` → 逐檔 parse → `resolve.from_files()` 建索引 → `to_edges()` → `build()`。 |
| P2 | 逐檔 parse 時以 `for_path()` 查 registry，查不到就跳過（不是失敗）。 |
| P3 | 讀檔用 `encoding="utf-8", errors="surrogateescape"`——讀不出 UTF-8 的位元組原樣留著，交給 parser 回報。 |
| P4 | 解析失敗的訊息貼回對應 `file` 節點的 `properties["parse_error"]`。 |
| P5 | resolve **依語言分組**呼叫，各用各的 resolver。 |
| P6 | 三個計數包成 `Diagnostics` 交給 `build()`。 |

P4 是管線唯一偏離「單向」的地方：scan 產出的節點會等 parse 跑完才交給 build。不讓 build 做這件事，是因為 build 的定位是「不在乎節點從哪來」。

P5 目前只有一組（Python），仍寫成迴圈——加語言時這裡不用改。

---

## 4. 錯誤

| 狀況 | 狀態碼 | 回給前端 | 日誌 |
|---|---|---|---|
| 路徑不在 allowlist 內／不存在／不是目錄／清單未設定 | `400` | `路徑不被允許` | `warning` ＋ traceback |
| 組圖失敗（`BuildError`） | `500` | `分析失敗` | `exception` |
| 請求形狀不合（缺 `path`、`externals` 值不對） | `422` | FastAPI 預設 | — |

`BuildError` 是**管線自己產出了不一致的圖**，不是使用者給錯東西，所以是 500 而不是 400。

> **詳細原因只寫進日誌。** 回「`/etc` 不在允許清單 `/home/user/project` 內」等於把 allowlist 內容與目錄結構送出去，試幾次就能把伺服器的檔案系統摸清楚。所以四種被拒絕的情況**共用同一句話**。

---

## 5. 不變式

| # | 保證 |
|---|---|
| I1 | 回應主體恆為 `GraphDocument`，不因收合或篩邊而換形狀。 |
| I2 | 對外的錯誤訊息**不含**絕對路徑、allowlist 內容或例外細節。 |
| I3 | 四種被拒絕的情況回應完全相同，無法用來探測路徑存不存在（見 `ingest.md` I3）。 |
| I4 | 不帶 `level`／`edge_types`／`externals` 的請求，回傳的就是 `build()` 出來的整張圖。 |
| I5 | 端點不改動任何檔案，也不在伺服器上留下分析結果。 |

---

## 6. 驗證

| 測試檔 | 筆數 | 涵蓋 |
|---|---|---|
| `tests/test_api_analyze.py` | 5 | A5–A9、400／500 的訊息、I2 |
| `tests/test_pipeline.py` | 8 | P1–P6 |
| `tests/test_smoke.py` | — | `/api/ping` |

`pipeline.analyze()` 是純函式，**不啟動 FastAPI 就能測**——目前 httpx 未安裝、`TestClient` 用不了，這一點特別實際。

---

## 7. 附錄：設計理由

### 7.1 為什麼路由定義與註冊分開（A1、A2）

不是分層儀式——分開之後，各 API 模組**彼此不需要知道對方存在**，新增一個不會動到既有的任何一個。

### 7.2 為什麼 `response_model` 一定要宣告（A4）

```python
@router.post("/api/analyze", response_model=GraphDocument)
```

不宣告也能動、回傳的 JSON 也一樣，但 `/openapi.json` 裡就**不會有這個型別**，日後想從它生成前端的 `types.ts` 會什麼都生不出來。而且這個疏漏不報錯，很難發現。

### 7.3 視圖就是幾個欄位

前端切換層級、外部套件模式、邊型別，改的都是 **request 的欄位**，不是換一個端點。這是「視圖 ＝ 同一張圖的查詢條件」在 API 上的樣子。

### 7.4 為什麼管線不放在這一層

| | |
|---|---|
| 為什麼分開 | API 層不該知道管線有幾段。管線多一段（parse、resolve）不該讓 HTTP 層跟著改 |
| 換到什麼 | `analyze(root) -> CodeGraph` 是純函式，測試不必啟動 HTTP 伺服器 |

---

## 8. 未定之處

| 項目 | 缺什麼 |
|---|---|
| 大型 repo 的回應 | 目前同步、一次回全部。上萬檔案時可能撐爆瀏覽器或逾時，屆時才需要工作 id 與輪詢 |
| zip 上傳端點 | 階段 3。需要 multipart 與 `ingest.from_zip()` |
| 存檔相關端點 | `store.save()` / `load()` 目前只是函式，沒有對應端點；要不要開、`data/` 放哪都未定 |
| 快取 | 同一個路徑重複分析會完整重跑一次。目前規模不需要 |
