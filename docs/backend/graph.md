# graph.md

`app/graph/` 這一層：把節點與邊清單組成一張圖、驗證它、算出 `meta`，並且是外界碰得到圖的唯一入口。

各階段職責見 CLAUDE.md › 架構 › build；序列化形狀見 `graph_schema.md`。

---

## 對外只有 `CodeGraph`

```
nodes + edges  →  build()  →  CodeGraph（networkx 包在裡面）
```

**networkx 物件不外露。`CodeGraph` 的方法一律回 `app/models/` 的型別。**

這條規則是「日後換 Neo4j / Kuzu 不必動上層」整個論證的支點。一旦某個方法回了 `nx.MultiDiGraph`，呼叫端就開始使用 networkx 的 API，換資料庫時那些地方全部要重寫 —— 抽象等於裝飾品。

`CodeGraph` 定義在 `query.py` 而不是 `build.py`：它就是查詢層那個介面，`build.py` 只管組與驗。查詢方法是 plan 1.6，屆時往這個類別加，不必搬家。

---

## 為什麼是 `MultiDiGraph`

「有向」與「可多重邊」是兩個獨立性質，networkx 用四個類別組合。我們兩個都要。

| | 需要的理由 |
|---|---|
| 有向 | `contains` 是父 → 子；`imports` 是誰依賴誰。循環偵測也靠方向 —— `A → B` 與 `B → A` 同時存在才叫循環 |
| 可多重邊 | 同一個檔案 import 同一個模組兩次，就是兩條邊帶不同行號。`calls` 更明顯：CLAUDE.md 說「被呼叫 n 次就是 n 條邊」 |

`DiGraph` 遇到重複的一對節點會**安靜地覆蓋**，不報錯，只是圖裡少了幾條邊。階段 1 只有 `contains`、不可能有平行邊，所以現在選它沒有任何代價，之後也不必回頭改。

---

## 驗證

| 擋什麼 | 為什麼 |
|---|---|
| 邊指向不存在的節點 | resolve 出錯時最容易產生這種邊。圖裡多出憑空的節點會讓後面每一個查詢都不準 |
| 節點 id 重複 | 同一個 id 兩份資料，之後取到哪一份看運氣 |

**一次列出所有問題，不是遇到第一個就停。** 這類錯誤通常整批出現，一條一條修很痛苦。

失敗時丟 `BuildError`。與 ingest 一樣，這一層不認識 HTTP，狀態碼由 API 層決定。

---

## meta

| 欄位 | 怎麼算 |
|---|---|
| `node_count` / `edge_count` | 清單長度 |
| `cycles` | **只看 `imports` 子圖**。循環依賴是 imports 的性質，`contains` 是樹、不可能有環 |
| `isolated_nodes` | **仍保持空的**，定義未定 |
| `parse_failures` / `ambiguous_imports` / `unresolved_imports` | **不算，照抄**。由呼叫端以 `Diagnostics` 傳進來 |
| `analyzed_at` | 建圖當下的 UTC 時間 |

### 三個計數為什麼是照抄而不是算

它們是 parse 與 resolve 在做事的當下才知道的（哪個檔案語法錯、哪個名字有多個候選），事後從圖上看不出來。build 的定位是「不在乎節點與邊從哪來」，讓它去認識 parse 與 resolve 的概念會破壞那件事。

所以 `build()` 多收一個 `Diagnostics`（frozen dataclass，不跨邊界所以不用 pydantic），只負責抄進 `meta`。`store.load()` 讀檔時也要把檔案裡的數字包回去，否則讀一次就歸零。

### `isolated_nodes` 為什麼還空著

「孤立」有意義的定義是「在 `imports` 裡沒有任何關聯」。現在 `imports` 邊有了，但**定義還沒定**：目錄與 repo 節點本來就沒有 imports 邊，全算進去的話答案裡有一大半是噪音；只算 `file` 的話，`README.md` 這種不該 parse 的檔案又會全部上榜。要先決定「哪些型別算、看哪種邊」，見「未定之處」。

### `cycles` 的兩個實作細節

- 用 `nx.simple_cycles`。它在大圖上有**指數爆炸**的風險；階段 1 沒有 imports 邊所以碰不到，真的變慢時改用強連通元件（代價是語意從「每個循環」變成「這群節點互相纏在一起」）。
- 每個循環會**旋轉成從 id 最小的節點開始**，外層再排序。`simple_cycles` 從哪個節點起算是任意的，不固定的話同一張圖跑兩次會產出不同的 JSON —— 與 scan 每層 `sorted()` 是同一個理由。

---

## 查詢層有哪些方法

| 方法 | 回傳 | 用途 |
|---|---|---|
| `document()` | `GraphDocument` | 整張圖。API 回傳與存檔都用它 |
| `view(*edge_types)` | `GraphDocument` | 篩邊型別。`view(CONTAINS)` 是目錄樹，`view(IMPORTS)` 是依賴圖 |

**「新增一種呈現方式 = 新增一組查詢條件」，`view()` 就是那句話的實作。**

### 篩邊之後節點全部保留

不砍掉沒有邊的節點 —— 「這個檔案存在，但沒有任何人 import 它」本身就是資訊，砍掉就看不見了。要不要畫出來是前端的事。

### `view()` 回的 `meta`

| 欄位 | 行為 |
|---|---|
| `node_count` / `edge_count` | 照這個視圖重算，否則前端拿到的數字跟畫面上的東西對不上 |
| `cycles` / `isolated_nodes` / `analyzed_at` | 沿用全圖的。那是整份分析的結論，不因為換個視圖就改變 |

### 還沒有的方法

`neighbors()`（誰用到我）、`path()`（A 怎麼連到 B）。CLAUDE.md 有列，但階段 1 沒有呼叫端，等真的要用再加。

---

## 存檔與讀回

`store.py` 兩個函式：

```
CodeGraph → save(path) → JSON 檔 → load(path) → CodeGraph
                                     └─ 走同一個 build()，同一套驗證
```

| 決定 | 為什麼 |
|---|---|
| 檔案位置與檔名**由呼叫端決定** | `data/` 的存放規則是 System_arch.md 的未定之處，不必為了這兩個函式提早拍板 |
| `load()` 把檔案裡的 `analyzed_at` 傳回 `build()` | 否則讀一次檔就會被記成一次新的分析，時間戳失去意義 |
| `cycles` 等其餘 `meta` 讀回時**重算** | 它們是衍生資訊。重算才能保證與節點邊的內容一致，而不是相信檔案裡寫的 |

---

## 分析路徑與讀取路徑共用這一段

`build()` 不在乎節點與邊從哪來：

| 路徑 | 輸入 |
|---|---|
| 分析 | scan（＋日後 resolve）的輸出 |
| 讀取 | JSON 反序列化出來的 `GraphDocument` |

所以讀回來的圖與剛分析出來的圖，走的是同一段驗證與同一套 `meta` 計算。這是 plan 1.8 要證明的事。

---

## 未定之處

| 項目 | 缺什麼 |
|---|---|
| 大圖的 `cycles` | 見上方。換成強連通元件的時機未定 |
| `neighbors()` / `path()` | CLAUDE.md 列在查詢層，但還沒有呼叫端，形狀未定 |
| 分析結果存在哪 | `save()` / `load()` 收路徑參數，但 `data/` 的位置、檔名規則與保留策略仍未定，見 System_arch.md |
