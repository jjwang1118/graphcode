# graph schema 規格

對應程式碼 `backend/app/models/`。職責的位置定義在 CLAUDE.md › 架構 › serialize。

**這份形狀是前後端唯一契約**，同時是磁碟儲存格式與 API 回傳格式。改它（加欄位、改欄位名、改 id 規則）就必須同步改 `frontend/src/api/types.ts`，否則前端會靜默拿到 `undefined`。

---

## 1. 職責

定義 `{ nodes, edges, meta }` 的形狀與 `id` 的組法。

| 做 | 不做 |
|---|---|
| 描述資料的形狀 | 驗證每條邊的兩端節點都存在（build 的事） |
| 提供 `make_id()` / `owner_file()` | 算 `meta` 的內容（build 的事） |
| 拒絕不合規的路徑 | 決定存到哪個檔案、檔名怎麼取（未定，見 `System_arch.md`） |

**只描述形狀，不認識任何生產者。**

---

## 2. 介面

### 2.1 模型

定義在 `app/models/graph.py`，對外由 `app/models/__init__.py` re-export。全部是 pydantic `BaseModel`。

| 模型 | 欄位 | 型別 | 預設 |
|---|---|---|---|
| `Node` | `id` | `str` | — |
| | `type` | `NodeType` | — |
| | `label` | `str` | — |
| | `properties` | `dict[str, Any]` | `{}` |
| `Edge` | `source` | `str` | — |
| | `target` | `str` | — |
| | `type` | `EdgeType` | — |
| | `properties` | `dict[str, Any]` | `{}` |
| `GraphDocument` | `nodes` | `list[Node]` | `[]` |
| | `edges` | `list[Edge]` | `[]` |
| | `meta` | `Meta` | `Meta()` |

`Meta` 的欄位見 §4。

根模型叫 `GraphDocument` 而非 `Graph`，是為了跟 `app/graph/` 裡的 networkx 圖區分：**它是跨越邊界的那份資料，不是圖本身。**

### 2.2 id 函式

定義在 `app/models/ids.py`。

| 名稱 | 簽章 | 說明 |
|---|---|---|
| `make_id` | `(node_type: NodeType, path: str, member: str \| None = None) -> str` | 組 id。不合規時丟 `ValueError` |
| `owner_file` | `(node_id: str) -> str \| None` | 反推所屬的 `file:` id |
| `PREFIX` | `dict[NodeType, str]` | 前綴的**唯一出處** |
| `ROOT_PATH` | `str` = `"."` | `repo` 節點的路徑基底 |
| `MEMBER_SEP` | `str` = `"::"` | 檔案內實體的分隔符 |

前綴推不出來也拼不出來，**一律呼叫 `make_id()`**。

---

## 3. 型別詞彙

定義在 `app/models/types.py`，兩個 `StrEnum`。序列化後就是原本的字串（`"file"`、`"contains"`），JSON 裡看不出是 enum。

| `NodeType` | 階段 |
|---|---|
| `repo` `directory` `file` `external_package` | 第一階段實際產出 |
| `module` `class` `function` | schema 已定義、尚未填充 |

| `EdgeType` | 階段 |
|---|---|
| `contains` `imports` | 第一階段實際產出 |
| `defines` `calls` `inherits` | schema 已定義、尚未填充 |

用 enum 而非自由字串，是因為 CLAUDE.md › 圖模型把型別列成**封閉清單**。理由與代價見 §8.1。

---

## 4. `meta`

整張圖只有一份，裝的是 build 算出來的**衍生資訊**，不是原始事實。

| 欄位 | 型別 | 預設 | 誰算的 |
|---|---|---|---|
| `node_count` | `int` | `0` | build |
| `edge_count` | `int` | `0` | build |
| `cycles` | `list[list[str]]` | `[]` | build。每個循環是一串 node id |
| `isolated_nodes` | `list[str]` | `[]` | build。**定義未定，目前恆空** |
| `parse_failures` | `int` | `0` | parse（經 `Diagnostics` 交給 build 照抄） |
| `ambiguous_imports` | `int` | `0` | resolve（同上） |
| `unresolved_imports` | `int` | `0` | resolve（同上） |
| `analyzed_at` | `datetime \| None` | `None` | build |

後三個是**準確度指標**：這張圖有多少成分是猜的、有多少東西根本沒讀到。個別是哪些看節點與邊的 `properties`（`parse_error`、`ambiguous`），見 `parse.md`、`resolve.md`。

build 只是把 `Diagnostics` 抄進來——它不認識 parse 與 resolve，數字由產生問題的那一層自己算。

### 刻意不放的

| 欄位 | 理由 |
|---|---|
| `root_path` | 伺服器上的絕對路徑，放進 API 回傳等於把本機檔案系統結構送給前端。真要有就放 `repo` 節點的 `properties`，由 API 層決定濾不濾 |
| `schema_version` | 目前只有一個版本，沒有人會讀它。真要處理舊檔時再加 |

---

## 5. id 規則

### 5.1 前綴

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

### 5.2 路徑 · `make_id`

| # | 規則 |
|---|---|
| R1 | 路徑一律**相對於 repo 根**。 |
| R2 | 分隔符固定 `/`；`\` 一律換成 `/`，Windows 也是。 |
| R3 | 去掉結尾的 `/`。 |
| R4 | `repo` 節點的路徑基底固定為 `.`。 |
| R5 | 空字串丟 `ValueError`。 |
| R6 | 開頭為 `/`，或首段含 `:`（擋 `C:/`），丟 `ValueError`。 |
| R7 | `member` 不為 `None` 時，以 `::` 接在路徑之後。 |

### 5.3 反推所屬檔案 · `owner_file`

| # | 規則 |
|---|---|
| R8 | 只切字串，不查表。取 `::` 之前的部分，換上 `file:` 前綴。 |
| R9 | 只有 `file`、`class`、`function` 三種型別回得出結果。 |
| R10 | `dir`、`ext`、`repo`、`module` 與無法辨識的 id 一律回 `None`。 |

| 輸入 | 回傳 |
|---|---|
| `class:src/app.py::Runner` | `file:src/app.py` |
| `file:src/app.py` | `file:src/app.py`（自己） |
| `dir:src`、`ext:fastapi`、`repo:.` | `None` |

---

## 6. 不變式

| # | 保證 |
|---|---|
| I1 | `GraphDocument()` 是一份合法的空圖——所有欄位都有預設值。 |
| I2 | id 全域唯一：前綴保證同名的目錄與檔案不會碰撞。 |
| I3 | id 不含伺服器的絕對路徑（R1、R6）。 |
| I4 | 同一份 source 換一個目錄存放，全圖的 id 不變。 |
| I5 | 加入新的節點／邊型別時，本層只需在 `types.py` 加一列、`ids.py` 加一列；`GraphDocument` 的形狀不變。 |

I5 是 CLAUDE.md「加入新型別時應該只動 parse 層」的本層對應——**`type` 是資料，不是結構**。要避免的是 `{ files, classes, functions, imports, calls }` 那種每加一種型別就得改結構、每個讀取的地方都得多處理一個陣列的形狀。

---

## 7. 驗證

| 測試檔 | 筆數 | 涵蓋 |
|---|---|---|
| `tests/test_models_ids.py` | 9 | R1–R10 |
| `tests/test_models_graph.py` | 6 | I1、JSON 的鍵剛好是契約上那些 |

`test_json_has_exactly_the_contracted_keys` 會在 `Meta` 加欄位時失敗。**那是刻意的**：它是提醒去同步改 `frontend/src/api/types.ts` 的閘門。

---

## 8. 附錄：設計理由

### 8.1 為什麼型別用 enum

CLAUDE.md › 圖模型把型別列成封閉清單。代價是新增一種型別要動 `types.py` 一列、`ids.py` 一列（節點型別才需要）——兩處都在 `app/models/` 之內，且都是**加一列而非改邏輯**，serialize 與前端組圖的迴圈都不動。

### 8.2 為什麼 `meta` 的欄位寫死、`properties` 開放

`properties` 開放是因為它**每個節點都不一樣**（行數、語言、import 在第幾行）；`meta` 整張圖只有一份、欄位少、變動慢，開放換不到彈性，只換到前端失去型別——`Record<string, unknown>` 會讓 `meta.nodeCount` 這種錯字編譯得過、執行時變 `undefined`。

### 8.3 為什麼 id 以檔案路徑為基底

「取 `::` 前的部分」就能反推所屬檔案（R8），不必維護一張 id → file 的對照表。

### 8.4 自行決定的部分

以下兩點**沒有上位依據**，是實作時為了讓規則真的生效而自己定的。

| 決定 | 為什麼這樣做 | 推翻的代價 |
|---|---|---|
| R6：`make_id()` 收到絕對路徑就丟 `ValueError` | 「路徑相對於 repo 根」若只寫在文件裡就只是口號，總會有一個呼叫端漏掉。順帶保護 id 格式——路徑裡混進 `:` 會讓前綴解析錯位 | 改 `_normalize_path()` 與 `test_models_ids.py` 的 `test_make_id_rejects_paths_that_are_not_relative_to_the_root` |
| R10：`owner_file()` 對 `module:` 一律回 `None` | 第二階段 `__init__.py` 會讓 directory 也成為 module，路徑基底可能不是檔案。現在猜一個會猜錯，不如明確回 `None` | 把 `NodeType.MODULE` 加進 `_FILE_SCOPED`，並定出 package module 的處置 |

---

## 9. 未定之處

| 項目 | 缺什麼 |
|---|---|
| `module` 節點的 `owner_file()` | 路徑基底可能是檔案也可能是目錄。目前一律回 `None`，第二階段填 `module` 節點時再定 |
| `isolated_nodes` | 欄位在，定義未定，目前恆空。「孤立」是指沒有任何邊，還是只看 `imports`？見 `graph.md` |
| `properties` 的鍵 | 各階段各自決定放什麼，尚無約定。真的散掉再回頭收斂 |
