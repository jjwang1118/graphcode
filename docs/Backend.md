
# backend 文件

後端是**一條單向管線**：每一段只吃前一段的輸出，不回頭呼叫。所以文件也照管線切——一段一份，加上兩份橫切的（序列化契約、HTTP 層）。

各階段的**職責**定義在 CLAUDE.md › 架構，**檔案擺放**在 `System_arch.md`，`backend/` 底下那七份是各元件的**規格書**，格式見下方「規格書格式」。

---

## 對照表

| 文件 | 管線位置 | 這份文件真正在講的一件事 | 對應程式碼 |
|---|---|---|---|
| [backend/graph_schema.md](backend/graph_schema.md) | serialize（橫切） | **`type` 是資料，不是結構**——加一種節點型別不改 schema 形狀，只是 `nodes` 陣列多一種 `type` 值 | `app/models/` |
| [backend/ingest.md](backend/ingest.md) | ① ingest | **allowlist 是唯一的安全閘門**，且字串比對擋不住 `..`、同前綴、symlink 三種繞法 | `app/ingest/` |
| [backend/scan.md](backend/scan.md) | ② scan | **走訪完，圖的 `contains` 那一半就完整了**；忽略規則是雜訊過濾，與安全無關 | `app/scan/` |
| [backend/graph.md](backend/graph.md) | ③ build ＋ 查詢層 ＋ 視圖 ＋ 存檔 | **networkx 不外露**——查詢層一律回 `app/models/` 的型別，這是日後換圖資料庫的前提 | `app/graph/` |
| [backend/parse.md](backend/parse.md) | ③ parse | **失敗必須是顯性的**——`ast` 遇到語法錯誤是整份檔案歸零，所以失敗要標在節點上、也要計數 | `app/parsers/` |
| [backend/resolve.md](backend/resolve.md) | ④ resolve | **「外部」不是判斷出來的，是查不到的結果**——所以索引建錯，內部依賴會被靜靜地誤判成第三方套件 | `app/resolve/` |
| [backend/api.md](backend/api.md) | 出口（橫切） | **視圖是一個欄位，不是一個端點**；錯誤訊息對外一律模糊，詳細只進日誌 | `app/api/` |

`languages/` 沒有獨立文件——語言 registry 由 parse 與 resolve 共用，規格寫在 [parse.md](backend/parse.md) §2.3。

---

## 規格書格式

`docs/backend/` 底下每一份都照同一個骨架，**章節順序固定**。順序一致本身就是規格書的特徵：找「這個函式的簽章」永遠翻 §2，找「這樣做的理由」永遠翻附錄。

| # | 章節 | 放什麼 | 可省略 |
|---|---|---|---|
| 1 | 職責 | 一句話 ＋ 一張「做／不做」的邊界表 | 否 |
| 2 | 介面 | 公開的函式簽章、型別欄位、Protocol。與程式碼逐字對應 | 否 |
| 3 | 行為 | **編號規則**，每條一句、可驗證 | 否 |
| 4 | 產出的資料 | 這一層產生的節點／邊／`properties` 鍵 | 沒有產出時可省 |
| 5 | 錯誤與邊界情況 | 一張「情況 → 行為」的表 | 否 |
| 6 | 不變式 | 這一層對外的保證，編號 `I1`、`I2`… | 否 |
| 7 | 驗證 | 對應的測試檔、筆數、涵蓋哪些規則；有實測數字放這裡 | 否 |
| 8 | 附錄：設計理由 | 取捨、被推翻的方案、實測依據 | 沒有可爭議之處時可省 |
| 9 | 未定之處 | 尚未決定的事，與重新評估的時機 | 全部決定了才可省 |

### 三條寫法規則

| # | 規則 | 為什麼 |
|---|---|---|
| F1 | §3 的每一條都**編號**（`R1`、`B1`、`C1`…），前綴在一份文件內可依子系統分組 | 別的文件才引用得到，例如「見 `resolve.md` R16」。沒有編號就只能整段複述 |
| F2 | §3 與 §6 的每一條都必須**可驗證**——能對照程式碼，或能寫成一個測試 | 「應該要正確處理」不是規格，是願望 |
| F3 | **理由一律進 §8**，§1–§7 只講「是什麼」 | 理由與規則交織時，看的人得先讀完一段敘事才找得到那條規則。理由不刪，只是移到後面 |

### 一個對照

同一件事，改寫前後：

```
改寫前（散文）
  相對 import 照定義就是路徑相對，不必經過模組名。level 是往上幾層⋯⋯
  爬出專案外時不產生邊。Python 自己也不允許，那是原始碼的問題，硬造一個
  外部套件節點是在說謊。

改寫後（§3 規則 ＋ §8 理由）
  | R9  | 走路徑，不經過模組名。起點是匯入者所在的目錄，再往上爬 level-1 層。|
  | R12 | 爬出專案外時回 None，**不產生邊**，計入 unresolved。|

  §8.3 為什麼相對 import 走路徑（R9）
       相對 import 照定義就是路徑相對⋯⋯硬造一個外部套件節點是在說謊。
```

### 不適用的範圍

這個格式是給**後端元件**用的。`plan.md`（工作清單）、`System_arch.md`（目錄對應）、`Frontend.md`（前端）各有自己的結構，不套這個骨架。

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
| parse | Fact 要不要自己宣告它產生什麼邊（build 目前仍需 `Fact → 節點/邊` 的對應規則）。**第三種 Fact 出現時**重評 | `parse.md` §9 |
| parse | 動態 import 完全看不到，要不要至少標記「這個檔案有動態 import」 | `parse.md` §9 |
| resolve | 被 scan 忽略卻被 import 的目標，要不要跟真的第三方套件區分 | `resolve.md` §8 |
| resolve | 「取最近」是啟發式，不讀 `PYTHONPATH` / `setup.py` 的真實搜尋順序 | `resolve.md` §8 |
| 解析 | 忽略規則要不要改讀專案自己的 `.gitignore`；`*.min.js` 這種樣式比對 | `scan.md` §9 |
| 解析 | 硬連結會產生兩個節點指向同一份內容，目前不處理 | `scan.md` §9 |
| 解析 | 走訪遇到權限不足時 `PermissionError` 直接往上冒，整次分析失敗 | `scan.md` §9 |
| 存放 | 分析結果存哪、檔名規則、保留策略。目前 `save()` / `load()` 收路徑參數，所以還不必決定 | `graph.md` §9、`System_arch.md` |
| 查詢 | `neighbors()`（誰用到我）、`path()` 的形狀 | `graph.md` §9 |
| 衍生資訊 | `isolated_nodes` 的定義：哪些節點型別算、看哪種邊。目前恆空 | `graph.md` §9 |
| 效能 | 大圖的 `cycles` 用 `simple_cycles` 有指數爆炸風險，何時換強連通元件 | `graph.md` §9 |
| 視圖 | `externals="grouped"` 的那個節點要怎麼「點開展開」。名單已存在 `properties["packages"]` | `graph.md` §9 |
| API | 大型 repo 是否需要非同步（工作 id ＋ 輪詢）。目前同步 | `api.md` §8 |
| API | 存檔要不要開端點；zip 上傳端點（階段 3） | `api.md` §8 |
| 契約 | `properties` 的鍵沒有約定；`module:` 的 `owner_file()` 目前一律回 `None` | `graph_schema.md` §9 |
| 設定 | allowlist 目前只能來自環境變數 | `ingest.md` §9 |

### 已經解決、不要再翻出來的

| 曾經未定 | 現在的答案 |
|---|---|
| Python 用什麼解析 | 標準庫的 `ast`。零依賴、`level` 欄位直接可用；代價是解析失敗即整份檔案歸零，靠標記與計數補。見 `parse.md` |
| API 路徑、視圖參數、錯誤格式、同步或非同步 | `POST /api/analyze`、`edge_types` 欄位、400/500 固定訊息、同步。見 `api.md` |
| scan 要不要跟隨 symlink | 不跟隨，連節點都不產。見 `scan.md` |
| 讀回 JSON 要不要另一個 build | 不要，共用同一個。見 `graph.md` |
| `parse_error` 由誰貼到 file 節點上 | `pipeline.py` 的 `_annotated()`。scan 產節點、parse 產錯誤，兩者在管線匯流處會合，不進 build。見 `api.md` P4 |
| resolve 怎麼決定模組名的起點 | 不猜，每一種數法都登記。`__init__.py` 判斷起點的做法**實測後推翻**。見 `resolve.md` §9.1 |
| 收合要在前端還是後端做 | 後端。`collapse()` 是 `GraphDocument → GraphDocument` 的純函式，換層級＝重打一次 API。見 `graph.md` §3.4 |

---

## 文件管不到的缺口

以下不是設計未定，是**工具鏈還沒補**，都記在 [plan.md](plan.md)：

| 缺口 | 影響 |
|---|---|
| `requirements.txt` 不存在（plan 0.4） | 環境無法在另一台機器重現 |
| mypy 沒有 networkx 的型別 | `app/graph/` 裡的 networkx 呼叫不被檢查，兩處 import 掛了 `type: ignore` |
| httpx 未安裝 | 用不了 `TestClient`，API 測試是直接呼叫 handler，**沒有真的發出 HTTP 請求** |
| 沒有版本控制（plan 0.3） | 目前 15 個 py 檔、8 份文件都沒有歷史，改壞了沒有回頭路 |
