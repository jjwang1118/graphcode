# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 互動守則

以下五點優先於本文件其餘所有內容。

1. **低耦合優先** — 任何模組、函數或其他實作單位，都以低耦合為第一考量：依賴介面而非具體實作、不跨層直接碰內部狀態、每個單位都能單獨測試與替換。若某個做法會讓兩處必須同進同出地一起改，先講出來再決定。
2. **最小修改** — 只改必要之處。不順手重構、不調整無關的命名或格式、不擴大變更範圍；與當前需求無關的問題只回報，不逕行修好。
3. **先說明理解、取得同意再動作** — 進行任何實作、修改或執行動作前，先說明你對需求的理解以及打算怎麼做，等使用者同意後才實際執行。唯讀的查看與搜尋不在此限。
4. **文件要結構化** — 撰寫或修改任何文件時，以主題切分小節、下標題、用表格或條列呈現並列的項目，小節之間以 `---` 分隔。不要把不同主題的內容混在同一段長文字裡。**主題不同就分成不同檔案**，不要什麼都往同一份文件塞；動手前先說明打算開哪些檔案、各放什麼。
5. **動組件前先讀它的文件，動完只同步改到的地方** — 哪個組件對應哪一份文件見「目錄對應關係」，那裡也有完整的四條規則。文件是規格、程式碼是它的實作，**不讀就改等於在猜規格**；改完只更新這次真的動到的敘述，沒動到的不要順手改寫。跨兩個組件就兩份都讀、兩份都同步。發現規格本身寫錯或做不到，**先說**，不要逕自改文件去遷就實作。

## 專案目標

把一份 source（專案原始碼）建成一個**程式碼知識圖譜**：以統一的圖模型描述專案內的實體與它們之間的關係，並在網站上互動式探索。

重點不是「把檔案畫出來」，而是**能回答關係問題** — 這個東西被誰用到、改這裡會波及哪些地方、哪些模組互相循環依賴、某個外部套件滲透到專案的哪些角落。視覺呈現是這個圖的其中一種出口，不是目的本身。

### 圖模型

全專案只有一張圖，節點與邊都帶型別（typed property graph）：

- 節點：`{ id, type, label, properties }`
- 邊：`{ source, target, type, properties }`

型別分兩批。**第一階段實際產出**：

| 型別 | | 簡述 |
|---|---|---|
| `repo` | 節點 | 整個專案的根，一次分析只有一個 |
| `directory` | 節點 | 資料夾 |
| `file` | 節點 | 單一原始碼檔案，第一階段的主角 |
| `external_package` | 節點 | 對應不到專案內任何檔案的 import 目標（第三方套件、標準函式庫）。只有名字，沒有內部結構 |
| `contains` | 邊 | 檔案系統層的包含：`repo → directory`、`repo → file`、`directory → directory`、`directory → file`。只連直接的下一層，且除 `repo` 外每個節點只有一個 `contains` 父節點 — 這是「篩 `contains` 剛好得到一棵樹」的來源 |
| `imports` | 邊 | 檔案對檔案或對外部套件的依賴，方向是「誰依賴誰」 |

**schema 已定義、尚未填充** — 現在就要能表達，之後才實作：

| 型別 | | 簡述 |
|---|---|---|
| `module` | 節點 | 可被 import 的單位。多數情況與 `file` 一對一，但 Python 的 `__init__.py` 會讓一個 `directory` 也成為 module — 兩者不等價，所以分開 |
| `class` | 節點 | 類別宣告 |
| `function` | 節點 | 函式或方法宣告。`def foo():` 產生節點，`foo()` 不產生 |
| `defines` | 邊 | 程式碼層的宣告包含：**外層宣告 → 內層宣告**，`file` 算最外層。`file → class`、`file → function`（頂層函式）、`class → function`（方法）都是這條規則的實例；巢狀宣告則產生 `function → function`、`class → class`。與 `contains` 分開是為了保留「這是宣告」的語意，代價是**沿層級展開時兩種邊都要吃** |
| `calls` | 邊 | 函式呼叫，`function → function`。被呼叫 n 次就是 n 條邊，收合到上層時聚合成一條帶權重的邊 |
| `inherits` | 邊 | 類別繼承或介面實作，`class → class` |

加入新型別時應該**只動 parse 層**。serialize 與前端把型別當資料處理，不該為了多一種型別而改結構；若某次新增型別逼得它們跟著改，那是模型設計有問題，先講出來。（build 目前仍需一條 `Fact → 節點/邊` 的對應規則，是唯一的例外，見「架構 › 後端管線 › parse」。）

### 範例：同一份 schema，跨兩個階段

以這兩個檔案為例（為求簡短，省略 `directory` 節點與 `contains` 邊）：

```python
# src/app.py                      # src/utils/io.py
from src.utils import io          def read(): ...

class Runner:
    def run(self):
        io.read()
```

**第一階段**：

```json
{
  "nodes": [
    { "id": "file:src/app.py",      "type": "file", "label": "app.py" },
    { "id": "file:src/utils/io.py", "type": "file", "label": "io.py" }
  ],
  "edges": [
    { "source": "file:src/app.py", "target": "file:src/utils/io.py", "type": "imports" }
  ]
}
```

**第二階段**：

```json
{
  "nodes": [
    { "id": "file:src/app.py",      "type": "file",     "label": "app.py" },
    { "id": "file:src/utils/io.py", "type": "file",     "label": "io.py" },
    { "id": "class:src/app.py::Runner",            "type": "class",    "label": "Runner" },
    { "id": "function:src/app.py::Runner.run",     "type": "function", "label": "run" },
    { "id": "function:src/utils/io.py::read",      "type": "function", "label": "read" }
  ],
  "edges": [
    { "source": "file:src/app.py", "target": "file:src/utils/io.py", "type": "imports" },
    { "source": "file:src/app.py", "target": "class:src/app.py::Runner", "type": "defines" },
    { "source": "class:src/app.py::Runner", "target": "function:src/app.py::Runner.run", "type": "defines" },
    { "source": "file:src/utils/io.py", "target": "function:src/utils/io.py::read", "type": "defines" },
    { "source": "function:src/app.py::Runner.run", "target": "function:src/utils/io.py::read", "type": "calls" }
  ]
}
```

**key 完全相同**，只有陣列裡的項目變多、`type` 多了幾種值。所以 pydantic model、`frontend/src/api/types.ts`、前端組圖的迴圈全都不用改。

要避免的是這種形狀 —— 每多一種型別就多一個 key，每個讀取的地方都得跟著多處理一個陣列：

```json
{ "files": [...], "classes": [...], "functions": [...],
  "imports": [...], "defines": [...], "calls": [...] }
```

### 視圖不是圖

**「依賴圖」與「目錄樹」不是兩種圖，而是同一張圖的兩種視圖** — 分別篩選 `imports` 邊與 `contains` 邊。新增一種呈現方式等於新增一組查詢條件，不是新增一條管線。

### 儲存與查詢

分析結果以 JSON 持久化，載入後用 networkx 建圖。**所有查詢都必須經過查詢層介面**（鄰居、子圖、路徑、循環偵測等），API 與前端不直接操作 networkx 物件 — 這層隔離是為了日後換成圖資料庫（Neo4j / Kuzu）時不必動上層。



## 技術棧

- 後端：Python 3.11+ / FastAPI / networkx（建圖）/ pytest / ruff / mypy。**conda 只負責環境與 Python 版本**（`conda create -n codegraph python=3.11`），所有指令都在 `conda activate codegraph` 之後執行；**套件一律由 `requirements.txt` 管理**，以 `pip install -r requirements.txt` 安裝。新增套件時同步寫入 `requirements.txt` 並釘住版本。
- 前端：Vite + React + TypeScript / Cytoscape.js（繪圖）。
- 前後端分離，各自獨立啟動。
- **Python 用標準庫的 `ast`**，理由與代價見 `docs/backend/parse.md`。**其他語言仍未決定**——tree-sitter、各語言原生 parser、輕量正規掃描都還在選項內，可依語言各自不同，決定前不要在程式碼裡預設任何一種。parse 層以副檔名註冊到 registry，解析技術屬該層內部細節。

## 啟動開發環境

前後端各自獨立，開兩個終端機。

**後端**（`:8000`）：

```bash
cd backend
conda activate codegraph
CODEGRAPH_ALLOWED_ROOTS=/home/jjwang1118/project uvicorn app.main:app --port 8000 --reload
```

**前端**（`:5173`）：

```bash
cd frontend
npm run dev
```

開 http://localhost:5173 。vite 的 proxy 把 `/api` 轉到 `:8000`。

| 症狀 | 原因 |
|---|---|
| 所有路徑都回 `400 路徑不被允許` | 沒帶 `CODEGRAPH_ALLOWED_ROOTS`。**未設定＝全部拒絕**，見「安全性約束」 |
| 前端連得上、後端沒反應 | proxy 目標寫死 `:8000`，後端換 port 要同步改 `frontend/vite.config.ts` |
| `ModuleNotFoundError: app` | uvicorn 必須在 `backend/` 底下跑 |

uvicorn 改程式碼要自己重啟（或加 `--reload`）；vite 存檔即時生效。

## 架構

### 後端管線

一條單向管線：每一階段只吃前一階段的輸出，不回頭呼叫、不跨階段存取。因此每一段都能餵假輸入單獨測試，也能整段抽換而不動其他段。

```
   輸入：zip 上傳 / 本機路徑
        │
        ▼
   ┌──────────┐
   │  ingest  │
   └──────────┘
        │  根目錄路徑
        ▼
   ┌──────────┐
   │   scan   │
   └──────────┘
        │  ①送去 parse 的檔案清單
        │  ②file / directory 節點 ＋ contains 邊 ──┐
        ▼                                          │
   ┌──────────┐                                    │
   │  parse   │  逐檔案，只吃 ①                    │
   └──────────┘                                    │
        │  帶型別的事實（Import("fastapi") …）     │
        ▼                                          │
   ┌──────────┐                                    │
   │ resolve  │  需全域索引，等所有檔案 parse 完   │
   └──────────┘                                    │
        │  imports 邊                               │
        ▼                                          │
   ┌──────────┐                                    │
   │  build   │  ◄── ② 直接進來，不經 parse/resolve
   └──────────┘
        │  networkx 圖（已驗證、含 meta）
        ▼
   ┌──────────┐
   │serialize │
   └──────────┘
        │  JSON
        ▼
   輸出：存檔 / 回傳前端
```

---

### 語言 registry — parse 與 resolve 共用

兩層都需要 per-language 的實作：parse 要知道這個語言的 import 怎麼寫，resolve 要知道名字怎麼變成檔案（Python 找 `__init__.py`、TS 找 `index.ts` 與 tsconfig path alias、Go 讀 `go.mod` 的 module 前綴）。共用同一份 registry，以副檔名為 key，一筆同時掛兩者：

```python
LANGUAGES = {
    ".py": { "parser": PythonParser(), "resolver": PythonResolver() },
    ".ts": { "parser": TsParser(),     "resolver": TsResolver()     },
}
```

**新增語言 = registry 加一筆**，parse 與 resolve 的程式碼都不動。合成一筆而不是分成兩張表，是為了不可能只加一半（parser 有、resolver 漏掉會變成解析得出結果卻接不到節點）。

registry 裝的是**語言知識**（這個語言的 import 怎麼寫），對每個專案都一樣，parse 讀它不違反「parse 沒有全域視野」；**專案知識**（有哪些檔案、路徑為何）只有 resolve 拿得到。兩者都以參數傳入，不要做成可變的全域狀態。

---

### ingest · `backend/app/ingest/`

**輸入** zip 上傳 / 本機路徑 → **輸出** 一個根目錄路徑

| # | 要做的事 | 重點 |
|---|---|---|
| 1 | 取得目錄 | zip 解壓到暫存區；本機路徑直接使用，不複製 |
| 2 | 安全驗證 | 本機路徑必須落在 allowlist 內；zip 要防 zip-slip 與 zip bomb（見「安全性約束」） |
| 3 | 找出真正的根 | zip 通常多包一層，解開後若只有單一頂層資料夾要往下鑽一層 — 否則圖裡會多一個無意義的目錄節點，所有路徑都多一層前綴 |

**不做**：看檔案內容、判斷是否為合法專案、走訪目錄結構（那是 scan 的事）。

職責是交出一個**可以安全走訪的根目錄**。後續階段一律只看到一個目錄，不知道 source 原本是什麼 — 新增輸入方式（如 git clone）只該動這一層。

---

### scan

**輸入** 根目錄路徑 → **輸出** ①送去 parse 的檔案清單　②`file`/`directory` 節點 ＋ `contains` 邊

| # | 要做的事 | 重點 |
|---|---|---|
| 1 | 走訪根目錄 | |
| 2 | 套用忽略規則 | `.git`、`node_modules`、`__pycache__`、`dist` 等，這些連節點都不產生 |
| 3 | 產出節點與 `contains` 邊 | 目錄結構是走訪的副產物，不需要解析原始碼 |
| 4 | 決定 parse 要看哪些檔案 | 進圖但不 parse 是正常的（`README.md` 有 `file` 節點，沒有 import 可抽） |

**scan 跑完時，圖的 `contains` 那一半就已經完整了**；後面幾個階段都只是在補 `imports` 那一半。

---

### parse · `backend/app/parsers/`

**輸入** 單一檔案內容 → **輸出** 帶型別的事實（不是裸字串）

| # | 要做的事 | 產出什麼 |
|---|---|---|
| 1 | 抽出**宣告** — 這個檔案自己有什麼 | 如 `Defines("class", "Runner")`（第二階段）。直接變成**節點**，不經 resolve |
| 2 | 抽出**引用** — 用到了誰 | 如 `Import("fastapi")`，第二階段還有 `Calls`、`Inherits`。目標在別處，交給 resolve 才變成**邊** |

**兩個刻意的限制**：

| 限制 | 換來什麼 |
|---|---|
| 只看單一檔案、沒有全域視野（抽出 `"fastapi"` 時並不知道那是外部套件） | parser 能用「餵一段程式碼字串、斷言吐出的 fact 清單」獨立測試，不必準備假專案 |
| 完全不做路徑解析（即使看得出是相對 import 也只回報字串） | 「名字指向誰」的邏輯全部集中在 resolve 一處，不散落到每個語言 |

每個語言一個模組，由**語言 registry** 以副檔名為 key 取出對應的 parser。副檔名查不到就跳過。

回傳事實物件而非裸字串，是「新增型別只動 parse 層」能成立的前提 — 加新東西就是加一種 Fact，介面與既有 parser 都不動。但嚴格說 build 仍需要一條 `Fact → 節點/邊` 的對應規則；要讓那句話完全成立，得讓 Fact 自己宣告它產生什麼邊，讓 build 變成不認識具體型別的通用迴圈。**此點尚未決定。**

---

### resolve · `backend/app/resolve/`

**輸入** 帶來源檔案的事實 ＋ 全域檔案索引 → **輸出** `imports` 邊

角色相當於 linker：把字串接到圖上的節點。

| # | 要做的事 | 重點 |
|---|---|---|
| 1 | 專案內對得到 | 接到該 `file` 節點 |
| 2 | 對不到 | 造 `external_package` 節點（規則必須一致） |
| 3 | 依語言挑規則 | fact 要帶來源檔案，才能推得副檔名 → 用哪套規則；相對 import 也需要它 |

**這是整條管線準確度的瓶頸** — 前面解析得再對、這裡接錯檔案，圖就是錯的，所以也最需要測試：相對 import、`__init__.py` 讓資料夾成為模組、TS 的 `index.ts` 與 path alias、`import *`。

**名稱解析規則本身就是 per-language**，所以 resolve 和 parse 一樣逐語言擴充，由**語言 registry** 以副檔名為 key 取出對應的 resolver。

---

### build

**輸入** 節點清單 ＋ 邊清單 → **輸出** networkx 圖（已驗證、含 `meta`）

| # | 要做的事 | 重點 |
|---|---|---|
| 1 | 驗證 | 每條邊的兩端節點都必須存在。resolve 出錯時最容易產生指向不存在節點的邊，在這裡擋掉 |
| 2 | 算衍生資訊 | 循環依賴、孤立節點。這些不是原始事實而是算出來的，放進 `meta` |
| 3 | 封裝 | **對外只透過查詢層介面**（鄰居、子圖、路徑、循環偵測），API 與前端不得直接操作 networkx 物件 — 這是日後換成 Neo4j / Kuzu 的前提 |

build 不在乎節點與邊從哪來，**因此分析路徑與讀取路徑共用同一個 build**：分析時吃 resolve 的輸出，讀取時吃 JSON 反序列化的結果（見「儲存與查詢」）。

---

### serialize · `backend/app/models/`

**輸入** 圖 → **輸出** JSON

以 pydantic 定義 `{ nodes, edges, meta }`，把記憶體裡的圖變成跨越邊界的資料。這份形狀同時是**磁碟儲存格式**與 **API 回傳格式**：形狀相同、內容不同（磁碟存全量，API 回傳篩過的視圖），前端因此只需要認識一種形狀。

| # | 設計要點 | 重點 |
|---|---|---|
| 1 | **`type` 是資料，不是結構** | 不要寫成 `{ files, directories, imports, classes }` 那種每加一種型別就得改結構的形狀。第二階段加 `class` / `calls` 時這份 schema 一個欄位都不用改，只是 `nodes` 陣列裡多出 `"type": "class"` 的項目 — 見「圖模型 › 範例」 |
| 2 | **`id` 帶型別前綴，且一律以檔案路徑為基底** | `file:src/app.py`、`dir:src`、`ext:fastapi`；檔案內的實體用 `::` 接續，如 `class:src/app.py::Runner`。前綴保證全域唯一（同名的目錄與檔案不會碰撞）；以檔案路徑為基底則讓「取 `::` 前的部分」就能反推所屬檔案，不必維護對照表 |
| 3 | **`properties` 是開放袋子**，`meta` 放衍生資訊 | 行數、語言、import 在第幾行放 `properties`，不影響 schema 形狀；節點邊數量、循環清單、分析時間放 `meta`，那些是 build 算出來的，不是原始事實 |

**這份 schema 是前後端唯一契約**，改它（加欄位、改欄位名、改 id 規則）就必須同步改 `frontend/src/api/types.ts`，否則前端會靜默拿到 `undefined`。它獨立成一個階段、而不是散在 build 裡順手 `json.dumps`，就是為了讓契約只有一個地方要看。

---

### 前端

- Cytoscape 實例存在 **ref**，不要放進 React state — 讓 React 重新渲染整張圖會失去使用者的 pan/zoom 與選取狀態。React 只負責餵入 elements 與觸發 layout。
- API 回傳的 `{nodes, edges}` 與 Cytoscape 的 element 格式不同，轉換集中在 `src/graph/transform.ts`，元件不直接碰 API 型別。
- 大型 repo 節點數會爆炸，畫布層要預期上千節點：預設收合、依目錄分群，別假設全部畫得完。

## 安全性約束

這兩點是設計上的硬性要求，不是一般性提醒：

- **本機路徑模式僅限開發用**，必須由環境變數的允許清單（allowlist）閘控。沒有閘控就等於開放任意檔案系統讀取給任何能打到 API 的人。
- **zip 解壓要防 zip-slip**（entry 路徑逃逸出解壓目錄），並對壓縮後大小、解壓後總大小、檔案數量設上限，避免 zip bomb。

## 目錄對應關係

哪一層放什麼檔案定義在 **`docs/System_arch.md`**，此處不重複。頂層為 `backend/`、`frontend/`、`docs/` 三者並列。

### 組件 → 對應文件

| 組件 | 程式碼 | 文件 |
|---|---|---|
| ingest | `backend/app/ingest/` | `docs/backend/ingest.md` |
| scan | `backend/app/scan/` | `docs/backend/scan.md` |
| parse | `backend/app/parsers/` | `docs/backend/parse.md` |
| resolve | `backend/app/resolve/` | `docs/backend/resolve.md` |
| 語言 registry | `backend/app/languages/` | `docs/backend/parse.md` ＋ `docs/backend/resolve.md`（各講自己那一半） |
| build／查詢層／收合／存檔 | `backend/app/graph/` | `docs/backend/graph.md` |
| serialize（schema、id 規則） | `backend/app/models/` | `docs/backend/graph_schema.md` |
| API 與管線編排 | `backend/app/api/`、`main.py`、`pipeline.py` | `docs/backend/api.md` |
| 後端全體（規格書格式、跨元件的決定） | `backend/` | `docs/Backend.md` |
| 前端全體（資料流、視覺編碼、畫布、互動、硬性規則） | `frontend/src/` | `docs/Frontend.md` |
| 前後端契約 | `frontend/src/api/types.ts` ↔ `backend/app/models/` | `docs/backend/graph_schema.md` ＋ `docs/Frontend.md › 契約` |
| 目錄結構 | 全部 | `docs/System_arch.md` |
| 範圍與進度 | 全部 | `docs/plan.md` |

### 動程式碼前後

1. **動之前先讀對應文件。** 文件寫的是規格，程式碼是它的實作——不讀就改等於在猜規格。
2. **動之後同步文件，但只改這次真的動到的地方。** 沒動到的敘述不要順手改寫、不要重排、不要「順便修正」。
3. 改動跨兩個組件，就兩份都要讀、兩份都要同步。
4. 若實作後發現文件寫的規格是錯的或做不到，**先說**，不要逕自改文件讓它符合程式碼。文件是規格，被實作倒過來覆寫的話就失去校準的作用了。