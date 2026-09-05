
# backend 文件

後端是**一條單向管線**：每一段只吃前一段的輸出，不回頭呼叫。所以文件也照管線切——一段一份，加上兩份橫切的（序列化契約、HTTP 層）。

各階段的**職責**定義在 CLAUDE.md › 架構，**檔案擺放**在 `System_arch.md`，這五份談的是**實作決定**。

---

## 對照表

| 文件 | 管線位置 | 這份文件真正在講的一件事 | 對應程式碼 |
|---|---|---|---|
| [backend/graph_schema.md](backend/graph_schema.md) | serialize（橫切） | **`type` 是資料，不是結構**——加一種節點型別不改 schema 形狀，只是 `nodes` 陣列多一種 `type` 值 | `app/models/` |
| [backend/ingest.md](backend/ingest.md) | ① ingest | **allowlist 是唯一的安全閘門**，且字串比對擋不住 `..`、同前綴、symlink 三種繞法 | `app/ingest/` |
| [backend/scan.md](backend/scan.md) | ② scan | **走訪完，圖的 `contains` 那一半就完整了**；忽略規則是雜訊過濾，與安全無關 | `app/scan/` |
| [backend/graph.md](backend/graph.md) | ③ build ＋ 查詢層 ＋ 存檔 | **networkx 不外露**——查詢層一律回 `app/models/` 的型別，這是日後換圖資料庫的前提 | `app/graph/` |
| [backend/parse.md](backend/parse.md) | ③ parse | **失敗必須是顯性的**——`ast` 遇到語法錯誤是整份檔案歸零，所以失敗要標在節點上、也要計數 | `app/parsers/` |
| [backend/resolve.md](backend/resolve.md) | ④ resolve | **「外部」不是判斷出來的，是查不到的結果**——所以索引建錯，內部依賴會被靜靜地誤判成第三方套件 | `app/resolve/` |
| [backend/api.md](backend/api.md) | 出口（橫切） | **視圖是一個欄位，不是一個端點**；錯誤訊息對外一律模糊，詳細只進日誌 | `app/api/` |

`languages/` 還沒有文件——語言 registry 是 plan 2.3，程式碼也還不存在。

---

## 脈絡：一次分析怎麼走

前端送 `POST /api/analyze {"path": "..."}`，接下來：

編排在 `app/pipeline.py`，不在 API 層——端點只負責換路徑與換狀態碼。

| # | 階段 | 文件 | 這一步做什麼 | 交出什麼 |
|---|---|---|---|---|
| 1 | ingest | [ingest.md](backend/ingest.md) | 判斷這個路徑准不准讀 | 一個可安全走訪的根目錄 |
| 2 | scan | [scan.md](backend/scan.md) | 走訪目錄、套用忽略規則 | `file` / `directory` 節點 ＋ `contains` 邊 |
| 3 | parse | [parse.md](backend/parse.md) | 逐檔案抽出事實（副檔名查不到 registry 就跳過） | `Import(...)` 的清單，或一句失敗原因 |
| 4 | resolve | [resolve.md](backend/resolve.md) | 把名字接到節點上 | `imports` 邊 ＋ `external_package` 節點 |
| 5 | build | [graph.md](backend/graph.md) | 驗證、組圖、算 `meta` | `CodeGraph`（networkx 包在裡面） |
| 6 | serialize | [graph_schema.md](backend/graph_schema.md) | 轉成跨得過邊界的形狀 | `{ nodes, edges, meta }` |
| 7 | 回應 | [api.md](backend/api.md) | 同步回整份 `GraphDocument` | HTTP 200 ＋ JSON |

**跑完第 2 步，目錄樹視圖的資料就齊了**——階段 1 刻意跳過 3 與 4，就是因為 `contains` 這一半不必碰最難的兩層。第 3、4 步補的是 `imports` 那一半。

實測本專案：119 節點（file 82 / dir 21 / ext 15 / repo 1）、334 條邊（contains 103 / imports 231）。


---

## 貫穿全部的四條規則

改任何一份文件之前，先確認沒有違反這四條：

| 規則 | 出處 | 破了會怎樣 |
|---|---|---|
| 安全檢查只在 ingest 一處 | `ingest.md` | 每多一種輸入方式（zip、git clone）都要自己記得檢查一次，漏一次就破功 |
| `type` 是資料不是結構 | `graph_schema.md` | 退化成 `{files, classes, imports}`，每加一種型別，所有讀取端都要多處理一個陣列 |
| networkx 不外露 | `graph.md` | 呼叫端開始用 networkx 的 API，換 Neo4j / Kuzu 時全部要重寫 |
| 對外的錯誤訊息不帶路徑 | `ingest.md`、`api.md` | 訊息變成探測工具，試幾次就能把伺服器的目錄結構摸出來 |

---

## 未定之處總表

各文件都有自己的「未定之處」，這裡彙整一次。**碰到時先確認，不要自行選定。**

| 主題 | 未定的事 | 在哪份文件 |
|---|---|---|
| parse | Fact 要不要自己宣告它產生什麼邊（build 目前仍需 `Fact → 節點/邊` 的對應規則）。**第三種 Fact 出現時**重評 | `parse.md` |
| parse | `parse_error` 由誰貼到 file 節點上（scan 產節點、parse 產錯誤，管線單向） | `parse.md` |
| resolve | 被 scan 忽略卻被 import 的目標，要不要跟真的第三方套件區分 | `resolve.md` |
| resolve | 「取最近」是啟發式，不讀 `PYTHONPATH` / `setup.py` 的真實搜尋順序 | `resolve.md` |
| 解析 | 忽略規則要不要改讀專案自己的 `.gitignore`；`*.min.js` 這種樣式比對 | `scan.md` |
| 解析 | 硬連結會產生兩個節點指向同一份內容，目前不處理 | `scan.md` |
| 存放 | 分析結果存哪、檔名規則、保留策略。目前 `save()` / `load()` 收路徑參數，所以還不必決定 | `graph.md`、`System_arch.md` |
| 查詢 | `neighbors()`（誰用到我）、`path()` 的形狀 | `graph.md` |
| 衍生資訊 | `isolated_nodes` 的定義：哪些節點型別算、看哪種邊。目前恆空 | `graph.md` |
| 效能 | 大圖的 `cycles` 用 `simple_cycles` 有指數爆炸風險，何時換強連通元件 | `graph.md` |
| API | 大型 repo 是否需要非同步（工作 id ＋ 輪詢）。目前同步 | `api.md` |
| API | 存檔要不要開端點 | `api.md` |
| 契約 | `properties` 的鍵沒有約定；`module:` 的 `owner_file()` 目前一律回 `None` | `graph_schema.md` |
| 設定 | allowlist 目前只能來自環境變數 | `ingest.md` |

### 已經解決、不要再翻出來的

| 曾經未定 | 現在的答案 |
|---|---|
| Python 用什麼解析 | 標準庫的 `ast`。零依賴、`level` 欄位直接可用；代價是解析失敗即整份檔案歸零，靠標記與計數補。見 `parse.md` |
| API 路徑、視圖參數、錯誤格式、同步或非同步 | `POST /api/analyze`、`edge_types` 欄位、400/500 固定訊息、同步。見 `api.md` |
| scan 要不要跟隨 symlink | 不跟隨，連節點都不產。見 `scan.md` |
| 讀回 JSON 要不要另一個 build | 不要，共用同一個。見 `graph.md` |

---

## 文件管不到的缺口

以下不是設計未定，是**工具鏈還沒補**，都記在 [plan.md](plan.md)：

| 缺口 | 影響 |
|---|---|
| `requirements.txt` 不存在（plan 0.4） | 環境無法在另一台機器重現 |
| mypy 沒有 networkx 的型別 | `app/graph/` 裡的 networkx 呼叫不被檢查，兩處 import 掛了 `type: ignore` |
| httpx 未安裝 | 用不了 `TestClient`，API 測試是直接呼叫 handler，**沒有真的發出 HTTP 請求** |
| 沒有版本控制（plan 0.3） | 目前 15 個 py 檔、8 份文件都沒有歷史，改壞了沒有回頭路 |
