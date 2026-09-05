# resolve 層的實作決定

resolve 把 parser 給的**字串**接到圖上的**節點**，角色相當於 linker：`Import(module='app.graph')` 進來，`file:backend/app/graph/__init__.py` 出去。職責定義在 CLAUDE.md › 架構 › resolve。

**這是整條管線準確度的瓶頸**——前面解析得再對，這裡接錯檔案，圖就是錯的，而且畫面上看不出來。所以這份文件的重點是：哪些地方會錯、錯了看不看得見。

對應程式碼 `backend/app/resolve/`。

---

## 核心問題：同一個檔案叫什麼名字

專案裡有 `external/CFRU/utils/fflow.py`，另一個檔案寫 `import utils.fflow`。這兩個是同一個東西嗎？取決於**從哪裡開始數**：

```
external / CFRU / utils / fflow
└──────────────────────────────┘  external.CFRU.utils.fflow
           └───────────────────┘  CFRU.utils.fflow
                   └───────────┘  utils.fflow   ← import 要的是這個
                           └───┘  fflow
```

起點（source root）在哪，**沒有寫在 import 語句裡**。所以整個 resolve 的設計就是在回答這件事。

---

## 索引：不猜起點，每一種數法都登記

| 登記的名字 | 指向 |
|---|---|
| `external.CFRU.utils.fflow` | `file:external/CFRU/utils/fflow.py` |
| `CFRU.utils.fflow` | 同上 |
| `utils.fflow` | 同上 |
| `fflow` | 同上 |

查詢時誰對得上算誰。`__init__.py` 自己不佔一段——它代表的是所在的目錄，所以 `a/b/__init__.py` 登記的是 `a.b` 與 `b`。

### 為什麼不用 `__init__.py` 判斷起點

原本的設計是「往上爬，遇到沒有 `__init__.py` 的目錄就停」。**實測後推翻。**

Python 3.3 之後不需要 `__init__.py` 也能 import（namespace package），而研究型專案幾乎都不寫：

| 專案 | `.py` 數 | `__init__.py` 數 |
|---|---|---|
| `poison-fru-sok-h100` | 18 | **0** |
| `llm` | 3 | **0** |
| `sven` | 126 | 3 |
| `UniversalNeuralCrackingMachines` | 20 | 1 |

以 `poison-fru-sok-h100` 為例，`external/CFRU/main.py` 寫著 `import utils.fflow`，而 `external/CFRU/utils/fflow.py` 確實存在。用 `__init__.py` 判斷起點會在第一層就停下，算出模組名 `fflow`，查 `utils.fflow` 落空，於是**專案內部的檔案被判成外部套件 `ext:utils`**——圖上少一條邊，而且無聲無息。

改成全部登記之後，這個專案解析出 22 條內部邊。

### 代價

短名字（`utils`、`main`、`config`）容易撞號。但這些撞號**本來就存在**——`import utils` 在一個有五個 `utils.py` 的 repo 裡本來就是模糊的。原本的做法不是解決了它，是判成外部套件、假裝看不到。

撞號會被標記（見下），判成外部不會。

---

## 解析規則

### 絕對 import：查模組名，先窄後寬

```python
from app.graph import build
   ① 查 app.graph.build   ← 有 build.py，中
   ② 查 app.graph
```

`name` 可能是子模組，所以先當子模組試，沒有才退回 package。順序反過來的話，`from app.graph.query import CodeGraph` 也會退化成指向 `__init__.py`，圖的解析度就沒了。

代價：`from app.graph import build` 的 `build` 其實是 `__init__.py` 轉出來的**函式**，卻會指向同名的 `build.py`。名字上不精確，但那個依賴實際存在（`__init__.py` 就是從 `build.py` 轉的），只是路徑上少繞一層。

### 相對 import：走路徑，不走模組名

相對 import 照定義就是路徑相對，不必經過模組名。`level` 是往上幾層：

| 原始碼 | 在 `app/graph/build.py` 裡 |
|---|---|
| `from . import query` | `app/graph/query` → `app/graph/query.py` |
| `from ..models import Node` | 往上一層 → `app/models/Node` 沒有 → 退回 `app/models` → `__init__.py` |

**爬出專案外時不產生邊**。Python 自己也不允許（`attempted relative import beyond top-level package`），那是原始碼的問題，硬造一個外部套件節點是在說謊。

### 查不到：外部套件，取最頂層

```python
import fastapi                        → ext:fastapi
from fastapi.routing import APIRoute  → ext:fastapi
```

`import fastapi` 與 `from fastapi.routing import X` 是同一個套件，該是同一個節點；取完整路徑會變成兩個互不相連的節點，看起來像兩個套件。

**完整路徑不會丟**，存在邊的 `properties["module"]` 裡。想知道用到哪些子模組，讀邊就有。

標準函式庫（`logging`）與第三方套件（`fastapi`）**在這裡不區分**，都是 `ext:`。要區分得再多一份標準函式庫清單，目前沒有需求。

> **「外部」不是判斷出來的，是查不到的結果。** 所以索引建錯的後果就是內部依賴被誤判成外部——見上面那個實測案例。

---

## 撞號：取最近的，並留下痕跡

同一個模組名對到多個檔案時，**取路徑上最近的**：比共同的目錄段數，多的贏。

```
匯入者    backend / app / graph / build.py
候選 A    backend / app / models / __init__.py   共用 2 段  ← 選這個
候選 B    tools   / app / models / __init__.py   共用 0 段
```

比的是「段」不是字元，否則 `back` 會看起來像 `backend` 的前綴。

平手時取排序後第一個——不是因為那樣猜得準，是為了**可重現**：同一個專案分析兩次要得到同一張圖。

### `ambiguous` 標記

撞號的邊帶上全部候選：

```json
{ "source": "file:backend/main.py", "target": "file:backend/app/__init__.py",
  "type": "imports",
  "properties": { "module": "app", "line": 3,
                  "ambiguous": ["file:backend/app/__init__.py",
                                "file:tools/app/__init__.py"] } }
```

記清單而不是布林值——只知道「這條邊不確定」查不下去，有候選才能人工判斷猜對沒有。

**它不是錯誤**：邊照樣產出，多數猜測是對的。它是信心標註，跟 `parse_error`（失敗，什麼都沒抽到）性質不同。

---

## 一筆 fact 一條邊

```python
from app.ingest import IngestError, allowed_roots_from_env, from_local_path
```

三筆 fact → **三條平行邊**，各自帶 `name` 與 `line`。圖用 `MultiDiGraph` 就是為了這個（見 `graph.md`）。

畫面上會有重疊的線，但**邊的聚合是視圖層的事**，不該在資料層先做掉——收斂成一條等於現在就把資訊丟掉。

### 不連沿路的 package

`import a.b.c` 在 Python 裡實際會載入 `a`、`a.b`、`a.b.c` 三個。我們**只連指名的那個**。

否則 `app/__init__.py` 會變成入邊最多的節點（幾乎每個檔案都寫 `from app.某某 import ...`），看起來像全專案最重要的檔案，但它是空的——那條邊表達的是「Python 的載入機制順便做了什麼」，會把真正的依賴訊號蓋掉。

---

## 兩個準確度指標

準確度本身沒辦法自動驗證（沒有標準答案可比對），這兩個數字是唯一拿得到的間接指標：

| 指標 | 意思 |
|---|---|
| `ambiguous` | 有幾條邊是從多個候選裡挑出來的 |
| `unresolved` | 有幾筆相對 import 爬出專案外，沒有產生邊 |

兩個都是 `ResolveResult` 的欄位。接進 `meta` 是之後接管線時的事。

---

## 實測

| | `codegraph` | `poison-fru-sok-h100` |
|---|---|---|
| `.py` 檔 | 41 | 18 |
| 解析失敗 | 0 | 0 |
| `imports` 邊 | 200（內部 143 / 外部 57） | 144（內部 22 / 外部 122） |
| 外部套件節點 | 15 | 29 |
| `ambiguous` | 0 | 0 |
| `unresolved` | 0 | 0 |

第二個專案沒有任何 `__init__.py`，那 22 條內部邊在原設計下會全部消失。

---

## 未定之處

| 主題 | 未定的事 |
|---|---|
| 被忽略卻被 import 的目標 | `node_modules`、`.venv` 等被 scan 排除的目錄，若被別的檔案 import，目前會查不到而變成 `ext:`。是否要區分「真的第三方」與「被我們排除掉的」尚未決定 |
| 動態 import | `__import__("x")`、`importlib.import_module()` 抓不到（parse 層的邊界），也就不會有邊 |
| `sys.path` 的真實順序 | 「取最近」是啟發式。專案若靠 `PYTHONPATH` 或 `setup.py` 指定搜尋順序，真實結果可能不同。目前不讀那些設定檔 |
| 標準函式庫 | `logging` 與 `fastapi` 都是 `ext:`，不區分 |
| `neighbors()` / `path()` | 查詢層還沒有這兩個開口（見 `graph.md`） |

---

## 自行決定的部分

| 決定 | 理由 | 推翻的代價 |
|---|---|---|
| 相對 import 走路徑而非模組名 | 相對 import 照定義就是路徑相對，繞模組名只會多一層轉換 | 改 `python.py` 的 `_relative` |
| 相對 import 對不到就退回 package 本身 | `from . import x` 至少代表「依賴這個 package」，這是真的 | 改候選清單 |
| 爬出專案外不計入 `ambiguous`，另計 `unresolved` | 一個是「有多個答案」，一個是「沒有答案」，混在一起數字沒有意義 | 改 `ResolveResult` |
| `ResolveResult` 不產生專案內的檔案節點 | 那些節點是 scan 產的，重複產一份會在 build 撞 id | 改 `to_edges` |
| 索引在 `from_files()` 一次建完 | 每筆 import 都是 O(1) 查表；後綴比對式的做法要嘛每次掃全部檔案，要嘛也得建索引 | 改 `index.py` |
