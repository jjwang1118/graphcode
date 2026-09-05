# scan 規格

對應程式碼 `backend/app/scan/`。職責的位置定義在 CLAUDE.md › 架構 › scan；節點 id 規則見 `graph_schema.md`。

---

## 1. 職責

走訪一個根目錄，把檔案系統變成節點與 `contains` 邊。

| 做 | 不做 |
|---|---|
| 產出 `repo` / `directory` / `file` 節點 | 檢查路徑准不准讀（ingest 的事） |
| 產出 `contains` 邊 | 看檔案內容、解析原始碼（parse 的事） |
| 交出要送去 parse 的檔案清單 | 挑哪些副檔名去解析（parse 以副檔名查 registry，查不到就跳過） |
| — | 驗證邊的兩端節點都存在、算 `meta`（build 的事） |

**scan 跑完時，圖的 `contains` 那一半就完整了**；後面幾個階段只補 `imports` 那一半。

---

## 2. 介面

| 名稱 | 簽章 | 說明 |
|---|---|---|
| `from_root` | `(root: Path, ignore: Collection[str] = DEFAULT_IGNORE) -> ScanResult` | 走訪並回傳三份輸出 |
| `is_ignored` | `(name: str, ignore: Collection[str] = DEFAULT_IGNORE) -> bool` | 名字比對 |
| `DEFAULT_IGNORE` | `frozenset[str]` | 預設忽略清單 |

| 型別 | 欄位 | 型別 | 意義 |
|---|---|---|---|
| `ScanResult` | `nodes` | `list[Node]` | `repo` / `directory` / `file` |
| | `edges` | `list[Edge]` | 只有 `contains` |
| | `files` | `list[str]` | 未被忽略的檔案的相對路徑，給 parse 用 |

忽略清單**以參數傳入**，`walk.py` 不認識任何具體的名字。

---

## 3. 行為

### 3.1 走訪

| # | 規則 |
|---|---|
| R1 | 根目錄本身產生一個 `repo` 節點，路徑基底固定為 `.`，`label` 為根目錄名。 |
| R2 | 每一層都以名字 `sorted()` 之後才走訪。 |
| R3 | 以下三種一律**跳過，連節點都不產生**：名字命中忽略清單、symlink、既不是目錄也不是一般檔案（socket、FIFO）。 |
| R4 | 目錄產生 `directory` 節點並遞迴進去；一般檔案產生 `file` 節點並登記進 `files`。 |
| R5 | 每個節點產生**一條**來自其直接父節點的 `contains` 邊，不連跨層的祖先。 |
| R6 | 空目錄照樣產節點。 |
| R7 | 節點的 `properties` 一律留空。 |
| R8 | 路徑一律相對於根、以 `/` 分隔（`Path.as_posix()`）。 |

### 3.2 忽略規則

| # | 規則 |
|---|---|
| R9 | 只比對**名字完全相符**，不做 `*.pyc` 這類樣式比對。 |
| R10 | 比對的是名字本身，不是路徑——任何一層叫這個名字都會被跳過。 |
| R11 | 預設清單：`.git`、`node_modules`、`__pycache__`、`dist`、`build`、`.venv`、`.mypy_cache`、`.pytest_cache`、`.ruff_cache`。 |

這是**雜訊過濾，與安全無關**——安全的閘門在 ingest。兩者刻意分開，理由見 §8.1。

---

## 4. 產出的資料

```
sample/                          repo:.            （label: sample）
├── src/          →              ├── dir:src
│   └── app.py                   │   └── file:src/app.py
└── README.md                    └── file:README.md
```

四個節點、三條 `contains` 邊，剛好一棵樹。

| 輸出 | 內容 |
|---|---|
| `nodes` | 上面四個，直接用 `app/models/` 的 `Node` |
| `edges` | `repo:.→dir:src`、`dir:src→file:src/app.py`、`repo:.→file:README.md` |
| `files` | `["README.md", "src/app.py"]` |

`files` 可以從 `nodes` 篩出來，仍然明列——parse 不必知道「節點有型別這回事」就能拿到它要的清單。

進圖但不 parse 是正常的：`README.md` 有 `file` 節點，沒有 import 可抽。

---

## 5. 錯誤與邊界情況

| 情況 | 行為 |
|---|---|
| 空目錄 | 產生 `directory` 節點，沒有子節點（R6） |
| symlink（指向目錄或檔案皆同） | 跳過，不產生節點（R3） |
| socket、FIFO 等特殊檔案 | 跳過，不產生節點（R3） |
| 忽略清單命中的目錄 | 整棵子樹都不走訪，裡面的檔案連 `files` 都不會有 |
| 硬連結 | **不處理**，看起來就是一般檔案，會產生兩個節點指向同一份內容 |
| 根目錄本身不存在 | 不在本層處理——ingest 已保證它存在（見 `ingest.md` I1） |

本層**不捕捉任何例外**。權限不足導致的 `PermissionError` 會直接往上冒，見 §9。

---

## 6. 不變式

| # | 保證 |
|---|---|
| I1 | 篩 `contains` 邊剛好構成**一棵樹**：`len(edges) == len(nodes) - 1`，且除 `repo` 外每個節點恰好有一個父。 |
| I2 | 同一個根目錄走訪兩次，`ScanResult` 完全相同（R2）。 |
| I3 | `files` 裡的每個路徑，都對應一個 `file:` 節點；反之亦然。 |
| I4 | 所有節點 id 的路徑都相對於根，不含絕對路徑。 |
| I5 | 走訪不會離開根目錄（R3 跳過 symlink）。 |

I5 補的是 `ingest.md` I1 留下的洞：ingest 只檢查入口那一個路徑。

---

## 7. 驗證

| 測試檔 | 筆數 | 涵蓋 |
|---|---|---|
| `tests/test_scan_walk.py` | 11 | R1–R8、I1、I2、symlink 與空目錄的處置 |

---

## 8. 附錄：設計理由

### 8.1 為什麼忽略規則與安全檢查分開

混在一起之後，沒人分得出哪條規則是為了擋攻擊、哪條只是為了畫面乾淨。改動「不想看到 `dist`」時就有機會順手弄壞安全規則。

`ignore.py` 單獨一個模組，是因為它是整個 scan **最可能被替換掉**的部分（之後可能改成讀專案自己的 `.gitignore`）；換掉它時 `walk.py` 一行都不動。

### 8.2 為什麼 symlink 不採「產節點但不遞迴」（R3）

`contains` 要求**每個節點恰好一個父**（I1）。一個指向別處的捷徑要掛在哪棵樹上沒有好答案，不如不進圖。

另外兩個實際問題：捷徑指向 allowlist 外會讓走訪逃逸；捷徑指回自己的祖先會讓走訪永遠走不完。

### 8.3 為什麼每一層都排序（R2）

檔案系統不保證 `iterdir()` 的回傳順序。不排序的話同一個 repo 跑兩次會產出不同的 JSON，golden 測試與 git diff 會一直髒。

### 8.4 為什麼空目錄照樣產節點（R6）

它仍是目錄樹的一部分。不產的話，畫出來的樹跟使用者在檔案總管看到的不一樣。

### 8.5 為什麼 `properties` 留空（R7）

行數、語言要開檔案讀，而 scan 的定義就是「不需要解析原始碼」。`properties` 是開放的袋子，需要時再加，不改 schema。

---

## 9. 未定之處

| 項目 | 缺什麼 |
|---|---|
| 樣式比對 | R9 只比對名字完全相符。`*.min.js`、`*.lock` 這類要靠樣式，尚未需要 |
| 讀專案自己的 `.gitignore` | 介面已預留（清單是參數），但沒有實作，也還沒決定要不要做 |
| 硬連結 | 會產生兩個節點指向同一份內容，目前不處理 |
| 權限不足 | `PermissionError` 目前直接往上冒，整次分析失敗。要不要改成跳過該目錄並記進 `meta` 尚未決定 |
