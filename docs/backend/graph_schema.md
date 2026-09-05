# graph_schema.md

序列化契約：`app/models/` 吐出的 `{ nodes, edges, meta }` 長什麼樣、`id` 怎麼組。

這份形狀同時是**磁碟儲存格式**與 **API 回傳格式**，也是 `frontend/src/api/types.ts` 的對照來源。改這裡就必須同步改前端，否則前端會靜默拿到 `undefined`。

各階段職責見 CLAUDE.md › 架構；HTTP 層見 `api.md`。

---

## 四個模型

定義在 `app/models/graph.py`，對外由 `app/models/__init__.py` re-export。

| 模型 | 欄位 |
|---|---|
| `Node` | `id: str`、`type: NodeType`、`label: str`、`properties: dict[str, Any]` |
| `Edge` | `source: str`、`target: str`、`type: EdgeType`、`properties: dict[str, Any]` |
| `Meta` | 見下方「meta」 |
| `GraphDocument` | `nodes: list[Node]`、`edges: list[Edge]`、`meta: Meta` |

根模型叫 `GraphDocument` 而非 `Graph`，是為了跟 `app/graph/` 裡的 networkx 圖區分：**它是跨越邊界的那份資料，不是圖本身。**

所有欄位都有預設值，`GraphDocument()` 是一份合法的空圖 —— build 尚未存在時也能建構來測。

---

## 型別詞彙

定義在 `app/models/types.py`，兩個 `StrEnum`。序列化後就是原本的字串（`"file"`、`"contains"`），JSON 裡看不出是 enum。

| `NodeType` | 階段 |
|---|---|
| `repo` `directory` `file` `external_package` | 第一階段實際產出 |
| `module` `class` `function` | schema 已定義、尚未填充 |

| `EdgeType` | 階段 |
|---|---|
| `contains` `imports` | 第一階段實際產出 |
| `defines` `calls` `inherits` | schema 已定義、尚未填充 |

用 enum 而非自由字串，是因為 CLAUDE.md › 圖模型把型別列成**封閉清單**。代價是新增一種型別要動 `types.py` 一列、`ids.py` 一列（節點型別才需要）—— 兩處都在 `app/models/` 之內，且都是加一列而非改邏輯，serialize 與前端組圖的迴圈都不動。

---

## id 規則

### 前綴

`ids.py` 的 `PREFIX` 是前綴的**唯一出處**。前綴推不出來也拼不出來，一律呼叫 `make_id()`。

| `NodeType` | 前綴 | 例子 |
|---|---|---|
| `repo` | `repo` | `repo:.` |
| `directory` | `dir` | `dir:src` |
| `file` | `file` | `file:src/app.py` |
| `external_package` | `ext` | `ext:fastapi` |
| `module` | `module` | `module:src/utils` |
| `class` | `class` | `class:src/app.py::Runner` |
| `function` | `function` | `function:src/app.py::Runner.run` |

前綴**不等於型別名**（`dir` ≠ `directory`、`ext` ≠ `external_package`），所以需要這張表。縮寫沿用 CLAUDE.md › serialize 設計要點 2 的既有例子。

### 路徑

| 規則 | 為什麼 |
|---|---|
| 一律**相對於 repo 根** | 用絕對路徑的話，同一份 source 換個目錄，全圖的 id 就全變，存檔讀不回來；也會把伺服器的檔案系統結構送到前端 |
| 分隔符固定 `/`，Windows 也是 | id 是跨機器的識別字，不能隨執行環境變形 |
| `repo` 節點的路徑基底是 `.` | 根自己的相對路徑就是 `.`。不用根目錄名，否則改資料夾名 id 就變；名字放 `label` 就夠了 |

`make_id()` 會把 `\` 換成 `/`、去掉結尾的 `/`，並在收到絕對路徑（開頭 `/` 或首段含 `:`）或空字串時丟 `ValueError`。

### 檔案內的實體

以 `::` 接在檔案路徑後：`class:src/app.py::Runner`。

因此 `owner_file()` 只要**切字串**就能反推所屬檔案，不必維護一張 id → file 的對照表：

| 輸入 | 回傳 |
|---|---|
| `class:src/app.py::Runner` | `file:src/app.py` |
| `file:src/app.py` | `file:src/app.py`（自己） |
| `dir:src`、`ext:fastapi`、`repo:.` | `None` |

---

## meta

整張圖只有一份，裝的是 build 算出來的**衍生資訊**，不是原始事實。

| 欄位 | 型別 | 預設 | 誰填 |
|---|---|---|---|
| `node_count` | `int` | `0` | build（plan 1.5） |
| `edge_count` | `int` | `0` | build |
| `cycles` | `list[list[str]]` | `[]` | build。每個循環是一串 node id |
| `isolated_nodes` | `list[str]` | `[]` | build。**定義未定，目前恆空** |
| `parse_failures` | `int` | `0` | parse（經 `Diagnostics` 交給 build 照抄） |
| `ambiguous_imports` | `int` | `0` | resolve（同上） |
| `unresolved_imports` | `int` | `0` | resolve（同上） |
| `analyzed_at` | `datetime \| None` | `None` | build |

後三個是**準確度指標**：這張圖有多少成分是猜的、有多少東西根本沒讀到。準確度本身沒辦法自動驗證（沒有標準答案可比對），這是唯一拿得到的間接訊號。個別是哪些看節點與邊的 `properties`（`parse_error`、`ambiguous`），見 `parse.md`、`resolve.md`。

build 只是把 `Diagnostics` 抄進來——它不認識 parse 與 resolve，數字由產生問題的那一層自己算。

### 為什麼欄位寫死

`properties` 開放是因為它每個節點都不一樣（行數、語言、import 在第幾行）；`meta` 整張圖只有一份、欄位少、變動慢，開放換不到彈性，只換到前端失去型別 —— `Record<string, unknown>` 讓 `meta.nodeCount` 這種錯字編譯得過、執行時變 `undefined`。

### 刻意不放的

| 欄位 | 理由 |
|---|---|
| `root_path` | 伺服器上的絕對路徑，放進 API 回傳等於把本機檔案系統結構送給前端。真要有就放 `repo` 節點的 `properties`，由 API 層決定濾不濾 |
| `schema_version` | 目前只有一個版本，沒有人會讀它。真要處理舊檔時再加 |

---

## 不在這一層做的事

| 事情 | 在哪做 | 為什麼不在這 |
|---|---|---|
| 驗證每條邊的兩端節點都存在 | `app/graph/build.py` | 那需要看過整份 nodes 才判斷得出來。models 只描述形狀，不認識任何生產者 |
| 算 `meta` 的內容 | 同上 | |
| 決定存到哪個檔案、檔名怎麼取 | 未定，見 `System_arch.md` › 未定之處的 `data/` | |

---

## 自行決定的部分

以下兩點**沒有上位依據**，是實作時為了讓規則真的生效而自己定的。要推翻只需改這裡與對應的測試，不牽動其他階段。

| 決定 | 為什麼這樣做 | 推翻的代價 |
|---|---|---|
| `make_id()` 收到絕對路徑就丟 `ValueError`（開頭 `/`，或首段含 `:` 擋掉 `C:/`） | 「路徑相對於 repo 根」若只寫在文件裡就只是口號，總會有一個呼叫端漏掉。順帶保護 id 格式 —— 路徑裡混進 `:` 會讓前綴解析錯位 | 改 `_normalize_path()` 與 `test_models_ids.py` 的 `test_make_id_rejects_paths_that_are_not_relative_to_the_root` |
| `owner_file()` 對 `module:` 一律回 `None` | 第二階段 `__init__.py` 會讓 directory 也成為 module，路徑基底可能不是檔案。現在猜一個會猜錯，不如明確回 `None` | 把 `NodeType.MODULE` 加進 `_FILE_SCOPED`，並定出 package module 的處置。見下方「未定之處」 |

---

## 未定之處

| 項目 | 缺什麼 |
|---|---|
| `module` 節點的 `owner_file()` | Python 的 `__init__.py` 會讓一個 directory 也是 module，路徑基底可能是檔案也可能是目錄。目前一律回 `None`，第二階段填 `module` 節點時再定 |
| `properties` 的鍵 | 各階段各自決定放什麼，尚無約定。真的散掉再回頭收斂 |
