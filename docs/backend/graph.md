# graph 規格

對應程式碼 `backend/app/graph/`。職責的位置定義在 CLAUDE.md › 架構 › build；序列化形狀見 `graph_schema.md`。

這一層有四個模組：`build.py`（組與驗）、`query.py`（查詢層介面）、`views.py`（篩邊與收合）、`store.py`（存檔讀回）。

---

## 1. 職責

把節點與邊清單組成一張圖、驗證它、算出 `meta`，並且是**外界碰得到圖的唯一入口**。

| 做 | 不做 |
|---|---|
| 驗證邊的兩端節點都存在 | 產生節點與邊（scan / resolve 的事） |
| 算衍生資訊（`cycles`、計數、時間） | 算 `parse_failures` 等三個計數（照抄，見 3.2） |
| 提供查詢與視圖 | 認識 HTTP、決定狀態碼（api 的事） |
| 存檔與讀回 | 決定存到哪、檔名怎麼取（呼叫端的事） |

> **networkx 物件不外露。`CodeGraph` 的方法一律回 `app/models/` 的型別。**

這條規則是「日後換 Neo4j / Kuzu 不必動上層」整個論證的支點，理由見 §8.1。

---

## 2. 介面

### 2.1 組圖 · `build.py`

| 名稱 | 簽章 |
|---|---|
| `build` | `(nodes: Sequence[Node], edges: Sequence[Edge], analyzed_at: datetime \| None = None, diagnostics: Diagnostics \| None = None) -> CodeGraph` |
| `Diagnostics` | frozen dataclass：`parse_failures: int = 0`、`ambiguous_imports: int = 0`、`unresolved_imports: int = 0` |
| `BuildError` | `Exception` |

### 2.2 查詢層 · `query.py`

| 方法 | 簽章 | 用途 |
|---|---|---|
| `CodeGraph.document` | `() -> GraphDocument` | 整張圖。API 回傳與存檔都用它 |
| `CodeGraph.view` | `(*edge_types: EdgeType) -> GraphDocument` | 篩邊型別 |
| `CodeGraph.meta` | 屬性，`Meta` | 全圖的 `meta` |

`CodeGraph` 定義在 `query.py` 而不是 `build.py`：它就是查詢層那個介面，`build.py` 只管組與驗。日後的查詢方法往這個類別加，不必搬家。

### 2.3 視圖 · `views.py`

純函式，`GraphDocument → GraphDocument`，**不碰 networkx**。

| 名稱 | 簽章 |
|---|---|
| `collapse` | `(document: GraphDocument, level: int \| None = None, externals: ExternalMode = "full") -> GraphDocument` |
| `only_edges` | `(document: GraphDocument, edge_types: Sequence[EdgeType]) -> GraphDocument` |
| `ExternalMode` | `Literal["full", "grouped", "hidden"]` |
| `GROUPED_EXTERNAL_ID` | `str` = `"ext:*"` |

### 2.4 存檔 · `store.py`

| 名稱 | 簽章 |
|---|---|
| `save` | `(graph: CodeGraph, path: Path) -> None` |
| `load` | `(path: Path) -> CodeGraph` |

---

## 3. 行為

### 3.1 驗證 · `build`

| # | 規則 |
|---|---|
| B1 | 節點 id 重複 → 丟 `BuildError`。 |
| B2 | 邊的 `source` 或 `target` 不在節點清單裡 → 丟 `BuildError`。 |
| B3 | **一次列出所有問題**，不是遇到第一個就停；訊息依 id 排序。 |
| B4 | 圖用 `nx.MultiDiGraph`。理由見 §8.2。 |
| B5 | 節點與邊的原始物件掛在 networkx 的屬性上（`node=` / `edge=`），查詢時原樣取回，不重建。 |

失敗丟 `BuildError`。與 ingest 一樣，這一層不認識 HTTP，狀態碼由 API 層決定。

### 3.2 算 `meta` · `build`

| # | 欄位 | 規則 |
|---|---|---|
| M1 | `node_count` / `edge_count` | 清單長度 |
| M2 | `cycles` | **只看 `imports` 子圖**，用 `nx.simple_cycles` |
| M3 | `cycles` 的每一圈 | 旋轉成從 id 最小的節點開始，外層再排序 |
| M4 | `isolated_nodes` | **恆為空**，定義未定（見 §9） |
| M5 | `parse_failures` / `ambiguous_imports` / `unresolved_imports` | **不算，照抄** `Diagnostics` |
| M6 | `analyzed_at` | 參數給了就用它，否則取當下的 UTC 時間 |

M2 只看 `imports` 是因為循環依賴是 imports 的性質，`contains` 是樹、不可能有環。

### 3.3 篩邊 · `CodeGraph.view` 與 `only_edges`

| # | 規則 |
|---|---|
| Q1 | 只保留指定型別的邊；`view()` 不給型別就是整張圖。 |
| Q2 | **節點一律全部保留**，不砍掉沒有邊的節點。 |
| Q3 | `node_count` / `edge_count` 依這個視圖重算；`cycles`、`isolated_nodes`、`analyzed_at` 與三個計數沿用全圖的。 |

Q2 的理由：「這個檔案存在，但沒有任何人 import 它」本身就是資訊，砍掉就看不見了。要不要畫出來是前端的事。

Q3 的理由：數量不重算的話，前端拿到的數字跟畫面上的東西對不上；其餘那些是**整份分析的結論**，不因為換個視圖就改變。

> **「新增一種呈現方式 ＝ 新增一組查詢條件」**，`view()` 與 `only_edges()` 就是那句話的實作。

### 3.4 收合層級 · `collapse`

`level` 是 `contains` 樹上的深度：**0 是 repo，1 是它的直接子項**，依此類推。

| # | 規則 |
|---|---|
| C1 | `level is None` 且 `externals == "full"` 時原樣回傳，不做任何事。 |
| C2 | 從 `contains` 邊建「子 → 父」對照表，每個節點往上爬到頂，鏈長就是它的深度。 |
| C3 | 深度 `<= level` 的節點**保留自己**；否則由第 `level` 層的祖先代表它。 |
| C4 | 只有「代表自己」的節點留在輸出裡，被收掉的節點消失。 |
| C5 | 每條邊的兩端都換成代表它的節點。 |
| C6 | 換完之後兩端相同（自環）的邊**不畫**。 |
| C7 | 換完之後重複的邊合成一條，筆數記在 `properties["weight"]`。 |
| C8 | 被 C6 丟掉的 `imports` 自環不是真的丟掉：計數記在該節點的 `properties["internal_imports"]`。 |
| C9 | `meta` 只更新 `node_count` / `edge_count`，其餘沿用（同 Q3）。 |
| C10 | 輸出的節點順序沿用輸入的順序；`grouped` 產生的那個節點排在最後。 |

C3 的「保留自己」是關鍵：根目錄下的 `README.md` 在 `level=2` 時上面沒有兩層目錄，**維持原樣**，不會憑空消失。

### 3.5 外部套件模式 · `externals`

在 C2/C3 算完之後套用，**與 `level` 無關**——收到目錄層時外部套件反而會變成節點的大宗（10 個目錄對 15 個套件），所以它需要自己的開關。

| # | 模式 | 規則 |
|---|---|---|
| E1 | `full` | 不動，每個套件各自一個節點 |
| E2 | `grouped` | 全部指向 `ext:*` 一個節點，`label` 為 `外部套件 (n)`，名單排序後放 `properties["packages"]` |
| E3 | `hidden` | 節點消失，**碰到它的邊一起消失** |

### 3.6 順序：先收合，後篩邊

`collapse()` 要靠 `contains` 邊算層級，所以**一定先收合再篩邊**。反過來的話，imports 視圖裡沒有 `contains` 邊，就收不動了。`api/analyze.py` 依這個順序呼叫。

### 3.7 存檔與讀回 · `store.py`

```
CodeGraph → save(path) → JSON 檔 → load(path) → CodeGraph
                                     └─ 走同一個 build()，同一套驗證
```

| # | 規則 |
|---|---|
| S1 | 存檔內容是 `document()` 的 JSON，縮排 2，UTF-8。 |
| S2 | `load()` 讀回後**重新走 `build()`**，檔案裡的圖若不合法就在這裡擋下來。 |
| S3 | `load()` 把檔案裡的 `analyzed_at` 傳回 `build()`，否則讀檔會被記成一次新的分析。 |
| S4 | `load()` 把三個計數包成 `Diagnostics` 傳回去，否則讀一次就歸零。 |
| S5 | `cycles` 等其餘 `meta` 讀回時**重算**——它們是衍生資訊，重算才能保證與節點邊的內容一致。 |

---

## 4. 產出的資料

`collapse()` 會往 `properties` 加三個鍵，都是收合才有的：

| 鍵 | 放哪 | 型別 | 意義 |
|---|---|---|---|
| `weight` | 邊 | `int` | 這條邊代表原本幾條（C7） |
| `internal_imports` | 節點 | `int` | 收合後落在這個節點內部的 import 筆數（C8） |
| `packages` | `ext:*` 節點 | `list[str]` | 被合併的套件名單，已排序（E2） |

`packages` 留著名單而不只留數量，是為了之後做「點開展開」時不必重新分析。

---

## 5. 錯誤與邊界情況

| 情況 | 行為 |
|---|---|
| 節點 id 重複 | `BuildError`，列出全部重複的 id |
| 邊指向不存在的節點 | `BuildError`，列出全部壞邊 |
| 空圖（沒有節點也沒有邊） | 合法，`meta` 全是預設值 |
| `level` 大於樹的最大深度 | 每個節點都「保留自己」，等同不收合 |
| `level = 0` | 全部收到 `repo` 一個節點，所有邊都變自環而消失 |
| 收合後某個節點沒有任何邊 | 照樣保留（同 Q2） |
| `externals="hidden"` 且某檔案只 import 外部套件 | 該檔案節點留著，邊全部消失 |
| 大圖的 `cycles` | `nx.simple_cycles` 有**指數爆炸**風險，見 §9 |

---

## 6. 不變式

| # | 保證 |
|---|---|
| I1 | `build()` 成功回傳的圖，每條邊的兩端節點必然存在（B2）。 |
| I2 | 分析路徑與讀取路徑走**同一個 `build()`**，因此讀回來的圖與剛分析出來的圖，驗證與 `meta` 計算完全相同。 |
| I3 | `save()` → `load()` → `save()` 的內容相同（S3、S4 保證計數與時間不流失）。 |
| I4 | 同一張圖算兩次 `cycles` 結果相同（M3）。 |
| I5 | **層級是累積的**：`level = n` 看得到的節點，`level = n+1` 一定也看得到。因為 C3 的條件是「深度 `<= level`」，深度沒變而門檻放寬。 |
| I6 | `collapse()` 與 `only_edges()` 不改動輸入的 `document`（純函式）。 |
| I7 | 收合前後，`imports` 的總筆數守恆：`Σ weight` ＋ `Σ internal_imports` ＝ 原本的 `imports` 邊數（`externals="hidden"` 除外，那會刻意丟掉一部分）。 |

I5 是「語意縮放」成立的前提：往下一層是**看得更細**，不是換一張圖。

---

## 7. 驗證

| 測試檔 | 筆數 | 涵蓋 |
|---|---|---|
| `tests/test_graph_build.py` | 11 | B1–B5、M1–M6 |
| `tests/test_graph_query.py` | 8 | Q1–Q3 |
| `tests/test_graph_views.py` | 12 | C1–C10、E1–E3、I5 |
| `tests/test_graph_store.py` | 3 | S1–S5、I3 |

### 收合的實測（本專案，`level=3`）

| | 檔案層 | 收到目錄層 |
|---|---|---|
| 節點 | 83 個 `file` | 10 個目錄 |
| 邊（聚合後） | 135 | 63 |
| 最忙節點的入邊 | **59**（`app/models/__init__.py`） | **7** |

59 條入邊的節點在畫面上就是一團蜘蛛網的中心。收到目錄層之後降到 7，因為「所有檔案都 import models」在目錄層本來就該是**一條**邊。

---

## 8. 附錄：設計理由

### 8.1 為什麼 networkx 不外露

一旦某個方法回了 `nx.MultiDiGraph`，呼叫端就開始使用 networkx 的 API，換資料庫時那些地方全部要重寫——抽象等於裝飾品。

### 8.2 為什麼是 `MultiDiGraph`（B4）

「有向」與「可多重邊」是兩個獨立性質，networkx 用四個類別組合。我們兩個都要。

| | 需要的理由 |
|---|---|
| 有向 | `contains` 是父 → 子；`imports` 是誰依賴誰。循環偵測也靠方向——`A → B` 與 `B → A` 同時存在才叫循環 |
| 可多重邊 | 同一個檔案 import 同一個模組兩次，就是兩條邊帶不同行號（見 `resolve.md` R16）。`calls` 更明顯：CLAUDE.md 說「被呼叫 n 次就是 n 條邊」 |

`DiGraph` 遇到重複的一對節點會**安靜地覆蓋**，不報錯，只是圖裡少了幾條邊。

### 8.3 為什麼三個計數是照抄而不是算（M5）

它們是 parse 與 resolve **在做事的當下才知道**的（哪個檔案語法錯、哪個名字有多個候選），事後從圖上看不出來。build 的定位是「不在乎節點與邊從哪來」，讓它去認識 parse 與 resolve 的概念會破壞那件事。

所以 `build()` 多收一個 `Diagnostics`（frozen dataclass，不跨邊界所以不用 pydantic），只負責抄進 `meta`。

### 8.4 為什麼 `cycles` 要旋轉起點（M3）

`simple_cycles` 從哪個節點起算是任意的，不固定的話同一張圖跑兩次會產出不同的 JSON——與 scan 每層 `sorted()` 是同一個理由。

### 8.5 為什麼 `views.py` 是純函式、不進 `CodeGraph`

收合只需要 `{nodes, edges}` 就算得出來，不需要 networkx 的任何能力。寫成純函式換到三件事：測試餵一份假 `GraphDocument` 即可、查詢層不必為它長胖、日後換圖資料庫時這個檔案完全不受影響。

### 8.6 為什麼自環要記成 `internal_imports` 而不是丟掉（C8）

收到目錄層時，`app/graph/build.py → app/graph/query.py` 會變成 `dir:app/graph → dir:app/graph` 的自環。畫出來沒有意義，但它代表「這個模組內部有多緊」——直接丟掉等於把資訊刪了。記在節點上，之後要用得到。

### 8.7 為什麼外部套件要有自己的開關（§3.5）

收合只收得動 `contains` 樹上的節點，而 `external_package` **不在那棵樹上**——它沒有父節點，永遠「保留自己」。所以層級調得再高，15 個套件節點還是全都在，收到目錄層時反而比目錄節點還多。

---

## 9. 未定之處

| 項目 | 缺什麼 |
|---|---|
| `isolated_nodes` | 「孤立」有意義的定義是「在 `imports` 裡沒有任何關聯」，但**哪些型別算、看哪種邊**還沒定：目錄與 repo 節點本來就沒有 imports 邊，全算進去的話答案裡一大半是噪音；只算 `file` 的話，`README.md` 這種不該 parse 的檔案又會全部上榜 |
| 大圖的 `cycles` | `nx.simple_cycles` 有指數爆炸風險。真的變慢時改用強連通元件，代價是語意從「每個循環」變成「這群節點互相纏在一起」。換的時機未定 |
| `neighbors()` / `path()` | CLAUDE.md 列在查詢層，但還沒有呼叫端，形狀未定 |
| 分析結果存在哪 | `save()` / `load()` 收路徑參數，但 `data/` 的位置、檔名規則與保留策略仍未定，見 `System_arch.md` |
| `grouped` 的展開 | `properties["packages"]` 已經留了名單，但「點開展開」的互動還沒做 |
