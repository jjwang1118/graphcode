# resolve 規格

對應程式碼 `backend/app/resolve/`。職責的位置定義在 CLAUDE.md › 架構 › resolve。

---

## 1. 職責

把 parser 給的**字串**接到圖上的**節點**，角色相當於 linker：`Import(module='app.graph')` 進來，`file:backend/app/graph/__init__.py` 出去。

兩張表，問的問題不同：

| 表 | 程式碼 | 回答 | 誰在問 |
|---|---|---|---|
| 模組索引 | `index.py` | 這個**模組名**是哪個檔案 | `Import` |
| 名字表 | `names.py` | 這個**名字**是哪個宣告 | `Inherits`（之後還有 `Calls`） |

兩者同一個模式：由 resolve 建、以參數傳入、parse 不必知道它存在。

| 做 | 不做 |
|---|---|
| 把模組名接到節點 id | 讀檔案內容（parse 的事） |
| 造對不到的 `external_package` 節點 | 造專案內的 `file` / `directory` 節點（scan 的事） |
| 計數 `ambiguous` / `unresolved` | 聚合平行邊（視圖層的事） |
| — | 讀 `sys.path`、`PYTHONPATH`、`setup.py`、`pyproject.toml` |

**這是整條管線準確度的瓶頸**：前面解析得再對，這裡接錯檔案，圖就是錯的，而且畫面上看不出來。

---

## 2. 介面

### 2.1 函式

| 名稱 | 簽章 | 說明 |
|---|---|---|
| `from_files` | `(files: Sequence[str]) -> ModuleIndex` | 從 scan 的檔案清單建索引。`files` 是相對於 repo 根的路徑 |
| `from_facts` | `(facts: Mapping[str, Sequence[Fact]], index: ModuleIndex, resolver: Resolver) -> NameIndex` | 從 parse 的事實建名字表。吃**整袋沒分型別的事實**，自己挑 `Defines` 與 `Import`——呼叫端因此不必提任何 Fact 型別 |
| `to_edges` | `(facts: Mapping[str, Sequence[Import]], index: ModuleIndex, resolver: Resolver) -> ResolveResult` | `facts` 以**來源檔案的節點 id** 為 key。**只吃 `Import`**——宣告不經 resolve，分流在 `app/facts/` 的表（見 `facts.md`），呼叫端是 `ImportProducer` |

### 2.2 型別

| 型別 | 欄位 | 型別 | 意義 |
|---|---|---|---|
| `Resolution` | `target` | `str` | 接到的節點 id |
| | `ambiguous` | `tuple[str, ...]` | 撞號時的**全部**候選（含 `target`）；不撞號為 `()` |
| `ModuleIndex` | `by_module` | `Mapping[str, tuple[str, ...]]` | 模組名 → 節點 id（排序過；多於一個代表撞號） |
| | `files` | `frozenset[str]` | 專案裡所有 `.py` 的相對路徑 |
| `ResolveResult` | `nodes` | `tuple[Node, ...]` | 只有 `external_package` |
| | `edges` | `tuple[Edge, ...]` | 只有 `imports` |
| | `unresolved` | `int` | 沒有產生邊的筆數 |
| | `ambiguous` | `int` | 從多個候選裡挑出來的筆數 |
| `Declaration` | `file` | `str` | 宣告所在檔案的 `file:` 節點 id |
| | `qualified` | `str` | 檔案內的完整路徑，如 `Runner.run` |
| | `kind` | `str` | parse 用的字串種類："class" / "function" |
| `Imported` | `module` | `str` | 目標模組的節點 id（`file:` 或 `ext:`） |
| | `member` | `str \| None` | 從那個模組裡取出的原名。整包 `import x` 為 `None` |
| `NameIndex` | `declared` | `Mapping[str, Mapping[str, Declaration]]` | 檔案 id → 完整路徑 → 宣告 |
| | `imported` | `Mapping[str, Mapping[str, Imported]]` | 檔案 id → 本地名 → 來源 |

全部為 frozen dataclass。

### 2.3 方法與協定

| 名稱 | 簽章 | 說明 |
|---|---|---|
| `ModuleIndex.lookup` | `(module: str, importer_id: str) -> Resolution \| None` | 絕對 import 用。查不到回 `None` |
| `ModuleIndex.at_path` | `(path: str) -> str \| None` | 相對 import 用。回節點 id |
| `NameIndex.lookup` | `(file_id: str, written: str) -> Declaration \| None` | 在這個檔案裡，這個名字指向哪個宣告。查不到回 `None` |
| `Resolver`（Protocol） | `target(fact: Import, importer_id: str, index: ModuleIndex) -> Resolution \| None` | 每個語言一個實作 |
| `PythonResolver` | 實作 `Resolver` | 由語言 registry 以副檔名取出 |

`ModuleIndex` 與 `NameIndex` 都是**專案知識**，一律以參數傳入，不得做成可變的全域狀態。

**`Resolver` 沒有為繼承長出第二個方法。** 「`Bar` 從哪個檔案來」就是解本檔那一
筆已經存在的 `Import`，所以 `from_facts` 直接呼叫 `resolver.target()`——相對
import、`__init__.py`、先窄後寬那些 per-language 規則一條都不必重寫。新增語言仍
然只是 registry 加一筆。

---

## 3. 行為

### 3.1 索引建立 · `from_files`

| # | 規則 |
|---|---|
| R1 | 只索引副檔名為 `.py` 的檔案，其餘一律忽略。 |
| R2 | 每個檔案登記**所有可能的模組名**：把路徑切段後，以每一段為起點各取一個後綴。`a/b/c.py` 登記 `a.b.c`、`b.c`、`c`。 |
| R3 | `__init__.py` 代表它所在的目錄，自己不佔一段。`a/b/__init__.py` 登記 `a.b`、`b`。 |
| R4 | 走訪順序為路徑排序，因此同一個模組名底下的候選清單也是排序過的。 |

### 3.2 絕對 import · `fact.level == 0`

| # | 規則 |
|---|---|
| R5 | 依序查兩個候選，先命中者為準：① `module.name`　② `module`。 |
| R6 | `fact.name` 為 `None`（如 `import x`、`from x import *`）時只查 `module`。 |
| R7 | 兩個都查不到時**不算失敗**，接到外部套件：`ext:` ＋ `module` 的**最頂層一段**。 |
| R8 | 標準函式庫與第三方套件不區分，都是 `ext:`。 |

先窄後寬的理由與代價見 §9.2。

### 3.3 相對 import · `fact.level > 0`

| # | 規則 |
|---|---|
| R9 | 走路徑，不經過模組名。起點是匯入者所在的目錄，再往上爬 `level - 1` 層。 |
| R10 | `fact.module` 不為空時，把 `.` 換成 `/` 接在起點之後。 |
| R11 | 依序查兩個候選，先命中者為準：① `base/name`　② `base`。每個候選都試 `<path>.py` 與 `<path>/__init__.py`，前者優先。 |
| R12 | 爬出專案外時回 `None`，**不產生邊**，計入 `unresolved`。 |

### 3.4 撞號 · 同一個模組名對到多個檔案

| # | 規則 |
|---|---|
| R13 | 取**路徑上最近**的：與匯入者共用的目錄段數最多者勝。比的是「段」不是字元。 |
| R14 | 平手時取候選清單排序後的第一個。 |
| R15 | 選中的邊必須帶 `properties["ambiguous"]`，內容是**全部**候選，並計入 `ResolveResult.ambiguous`。 |

R14 的目的是**可重現**，不是猜得準：同一個專案分析兩次必須得到同一張圖。

### 3.5 邊的產生 · `to_edges`

| # | 規則 |
|---|---|
| R16 | **一筆 fact 一條邊**。`from x import A, B, C` 產生三條平行邊，各自帶 `name` 與 `line`。 |
| R17 | 只連 `import` 指名的那個目標，**不連沿路的 package**。`import a.b.c` 只產生一條指向 `a.b.c` 的邊。 |
| R18 | 走訪順序為 `sorted(facts)`，邊的順序因此固定。 |
| R19 | `external_package` 節點依 id 去重，同一個套件只產生一個節點，輸出時依 id 排序。 |

---

### 3.6 名字表的建立 · `from_facts`

| # | 規則 |
|---|---|
| N1 | 每個檔案登記兩組：自己的**宣告**（key 是完整路徑，如 `Outer.Inner`）與 **import 進來的名字**（key 是本地名）。 |
| N2 | import 的本地名取 `alias` → `name` → `module`（整包 `import a.b.c` 登記 `a.b.c`，不是 `a`）。 |
| N3 | import 的目標走 `resolver.target()`，與 `imports` 邊用同一段程式碼；解不出來的那一筆不登記。 |
| N4 | 同一個名字被登記兩次時**後面的贏**，跟 Python 自己一樣（後定義的蓋掉前面的）。 |

### 3.7 名字表的查法 · `lookup`

查表順序就是 Python 自己的名字解析規則，少一層都會連錯：

| # | 規則 |
|---|---|
| N5 | ① 先查本檔宣告，完整路徑直接比對——`Outer.Inner` 這種查得到。 |
| N6 | ② 再查本檔 import 進來的名字。點狀名取**最長的前綴**當來源（`nx.Graph` 取 `nx`，`a.b.Foo` 取 `a.b`），剩下那一段去目標檔案的宣告裡找；沒有點的則用 import 時的原名（`from x import Bar as B`，寫 `B` 要找的是 `Bar`）。 |
| N7 | ③ 兩者都沒有就回 `None`。**沒有全域搜尋**。 |

**N7 是這張表最重要的一條。** 一個名字沒 import 進來就不在這個檔案的作用域裡，
跨檔案去找同名的東西會連出一堆假邊——同 §9.1 的那句「外部不是判斷出來的，是查
不到的結果」。

**這一版只到檔案層級**：本檔的宣告全部算看得到，不分函式內外，也不處理遮蔽。代
價是**巢狀類別以裸名被繼承時查不到**（`class Inner(AntiAtlasView)` 寫在
`Outer` 裡面，而 `AntiAtlasView` 也是 `Outer` 的成員），實測 networkx 有 2 筆。
作用域感知是 plan 5.5，表的形狀不必為它改。

---

## 4. 產出的資料

### 4.1 邊

型別一律為 `imports`，`source` 是匯入者的 `file:` id。

| `properties` 欄位 | 型別 | 出現時機 | 內容 |
|---|---|---|---|
| `module` | `str` | 一律 | 原始碼裡寫的字串，`from ..pkg import x` 為 `..pkg` |
| `line` | `int` | 一律 | import 在第幾行 |
| `name` | `str` | `fact.name` 不為 `None` 時 | `from x import y` 的 `y` |
| `ambiguous` | `list[str]` | 撞號時（R15） | 全部候選的節點 id |

```json
{ "source": "file:backend/main.py", "target": "file:backend/app/__init__.py",
  "type": "imports",
  "properties": { "module": "app", "line": 3,
                  "ambiguous": ["file:backend/app/__init__.py",
                                "file:tools/app/__init__.py"] } }
```

### 4.2 節點

只產生 `external_package`，`label` 為套件名（不含 `ext:` 前綴）。

---

## 5. 錯誤與邊界情況

| 情況 | 行為 | 計入 |
|---|---|---|
| 絕對 import 查不到 | 接到 `ext:<最頂層>` | — |
| 相對 import 爬出專案外 | 不產生邊 | `unresolved` |
| 相對 import 在專案內但檔案不存在 | 不產生邊 | `unresolved` |
| 同一個模組名對到多個檔案 | 產生邊，帶全部候選 | `ambiguous` |
| `from x import *` | `name` 為 `None`，接到 `x` 本身 | — |
| 被 scan 排除的目錄（`node_modules`、`.venv`）被 import | 索引裡沒有 → 變成 `ext:` | — |
| 動態 import（`importlib.import_module()`） | parse 抽不到 fact，這一層看不到 | — |

`ambiguous` **不是錯誤**：邊照樣產出，多數猜測是對的。它是信心標註，與 `parse_error`（什麼都沒抽到）性質不同。

---

## 6. 不變式

| # | 保證 |
|---|---|
| I1 | 同一個專案分析兩次，`ResolveResult` 完全相同（R4、R14、R18、R19）。 |
| I2 | 每條邊的 `source` 必然是 scan 產過的 `file:` 節點；`target` 必然是 scan 產過的 `file:` 節點或本層產出的 `ext:` 節點。build 會驗證這件事。 |
| I3 | 本層**不產生**專案內的 `file` / `directory` 節點。重複產一份會在 build 撞 id。 |
| I4 | 輸入的 fact 筆數 ＝ `len(edges)` ＋ `unresolved`。 |
| I5 | `Resolution.ambiguous` 非空時，`target` 必然在其中。 |

---

## 7. 驗證

| 測試檔 | 筆數 | 涵蓋 |
|---|---|---|
| `tests/test_resolve_index.py` | 9 | R1–R4、R13–R14、`at_path` |
| `tests/test_resolve_python.py` | 18 | R5–R12、R15–R19、`unresolved` / `ambiguous` 計數 |
| `tests/test_resolve_names.py` | 10 | N1–N7，含「另一個檔案有同名的 class 也不算」與「裸名查不到巢狀宣告」 |

準確度本身**沒辦法自動驗證**（沒有標準答案可比對）。`ambiguous` 與 `unresolved` 是唯一拿得到的間接指標。

實測結果：

| | `codegraph` | `poison-fru-sok-h100` |
|---|---|---|
| `.py` 檔 | 41 | 18 |
| 解析失敗 | 0 | 0 |
| `imports` 邊 | 200（內部 143 / 外部 57） | 144（內部 22 / 外部 122） |
| 外部套件節點 | 15 | 29 |
| `ambiguous` | 0 | 0 |
| `unresolved` | 0 | 0 |

---

## 8. 未定之處

| 主題 | 未定的事 |
|---|---|
| 被忽略卻被 import 的目標 | 被 scan 排除的目錄若被 import，會變成 `ext:`。是否區分「真的第三方」與「被我們排除掉的」尚未決定 |
| `sys.path` 的真實順序 | R13 是啟發式。專案若靠 `PYTHONPATH` 或 `setup.py` 指定搜尋順序，真實結果可能不同 |
| 標準函式庫 | R8 不區分。要區分得再多一份標準函式庫清單，目前沒有需求 |
| `neighbors()` / `path()` | 查詢層還沒有這兩個開口（見 `graph.md`） |

---

## 9. 附錄：設計理由

### 9.1 為什麼索引要登記每一種數法（R2）

專案裡有 `external/CFRU/utils/fflow.py`，另一個檔案寫 `import utils.fflow`。這兩個是同一個東西嗎？取決於**從哪裡開始數**：

```
external / CFRU / utils / fflow
└──────────────────────────────┘  external.CFRU.utils.fflow
           └───────────────────┘  CFRU.utils.fflow
                   └───────────┘  utils.fflow   ← import 要的是這個
                           └───┘  fflow
```

起點（source root）在哪，**沒有寫在 import 語句裡**。所以不猜，每一種數法都登記，誰對得上算誰。

原本的設計是「往上爬，遇到沒有 `__init__.py` 的目錄就停」，**實測後推翻**。Python 3.3 之後不需要 `__init__.py` 也能 import（namespace package），而研究型專案幾乎都不寫：

| 專案 | `.py` 數 | `__init__.py` 數 |
|---|---|---|
| `poison-fru-sok-h100` | 18 | **0** |
| `llm` | 3 | **0** |
| `sven` | 126 | 3 |
| `UniversalNeuralCrackingMachines` | 20 | 1 |

以 `poison-fru-sok-h100` 為例：`external/CFRU/main.py` 寫著 `import utils.fflow`，`external/CFRU/utils/fflow.py` 確實存在。用 `__init__.py` 判斷起點會在第一層就停下，算出模組名 `fflow`，查 `utils.fflow` 落空，於是**專案內部的檔案被判成外部套件 `ext:utils`**——圖上少一條邊，而且無聲無息。改成全部登記之後，這個專案解析出 22 條內部邊。

代價是短名字（`utils`、`main`、`config`）容易撞號。但這些撞號**本來就存在**——`import utils` 在一個有五個 `utils.py` 的 repo 裡本來就是模糊的。原本的做法不是解決了它，是判成外部套件、假裝看不到。撞號會被標記（R15），判成外部不會。

> **「外部」不是判斷出來的，是查不到的結果。** 索引建錯的後果就是內部依賴被誤判成外部。

### 9.2 為什麼先窄後寬（R5、R11）

```python
from app.graph import build
   ① 查 app.graph.build   ← 有 build.py，中
   ② 查 app.graph
```

`name` 可能是子模組，所以先當子模組試。順序反過來的話，`from app.graph.query import CodeGraph` 也會退化成指向 `__init__.py`，圖的解析度就沒了。

代價：`from app.graph import build` 的 `build` 若其實是 `__init__.py` 轉出來的**函式**，仍會指向同名的 `build.py`。名字上不精確，但那個依賴實際存在（`__init__.py` 就是從 `build.py` 轉的），只是路徑上少繞一層。

### 9.3 為什麼相對 import 走路徑（R9）

相對 import 照定義就是路徑相對，不必經過模組名，繞模組名只會多一層轉換。爬出專案外時 Python 自己也不允許（`attempted relative import beyond top-level package`），那是原始碼的問題，硬造一個外部套件節點是在說謊。

### 9.4 為什麼外部套件只取最頂層（R7）

`import fastapi` 與 `from fastapi.routing import APIRoute` 是同一個套件，該是同一個節點；取完整路徑會變成兩個互不相連的節點，看起來像兩個套件。**完整路徑不會丟**，存在邊的 `properties["module"]` 裡。

### 9.5 為什麼一筆 fact 一條邊（R16）

聚合會丟資訊——收斂成一條之後，`name` 與 `line` 就沒地方放了。圖用 `MultiDiGraph` 就是為了容納平行邊（見 `graph.md`）。畫面上會有重疊的線，但**邊的聚合是視圖層的事**，不該在資料層先做掉。

### 9.6 為什麼不連沿路的 package（R17）

`import a.b.c` 在 Python 裡實際會載入 `a`、`a.b`、`a.b.c` 三個。若照做，`app/__init__.py` 會變成入邊最多的節點（幾乎每個檔案都寫 `from app.某某 import ...`），看起來像全專案最重要的檔案，但它是空的——那條邊表達的是「Python 的載入機制順便做了什麼」，會把真正的依賴訊號蓋掉。

### 9.7 其他自行決定的部分

| 決定 | 理由 | 推翻的代價 |
|---|---|---|
| 相對 import 對不到就退回 package 本身 | `from . import x` 至少代表「依賴這個 package」，這是真的 | 改 `_candidates` 的候選清單 |
| 爬出專案外不計入 `ambiguous`，另計 `unresolved` | 一個是「有多個答案」，一個是「沒有答案」，混在一起數字沒有意義 | 改 `ResolveResult` |
| 索引在 `from_files()` 一次建完 | 每筆 import 都是 O(1) 查表；後綴比對式的做法要嘛每次掃全部檔案，要嘛也得建索引 | 改 `index.py` |
