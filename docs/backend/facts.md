# facts 規格

對應程式碼 `backend/app/facts/`。職責的位置定義在 CLAUDE.md › 架構 › facts。

這一層有五個模組：`production.py`（產生器的契約）、`producers.py`（型別 → 產生器的表與套用它的迴圈）、`declarations.py`（宣告 → 節點與邊）、`imports.py`（引用 → 交給 resolve）、`inherits.py`（繼承 → 邊）。

---

## 1. 職責

把 parse 交出來的**一袋不分型別的 Fact**，依型別分派給各自的產生器，合併成節點、邊與計數。

| 做 | 不做 |
|---|---|
| 依 `type(fact)` 分堆、查表、合併結果 | 決定管線有幾段、誰先誰後（`pipeline.py` 的事） |
| 宣告 → `class` / `function` 節點 ＋ `defines` 邊 | 名稱解析（resolve 的事） |
| 查到的宣告 → `inherits` 邊 | 建名字表（resolve 的事，表由 `Context` 帶進來） |
| 把 resolve 的結果換成產生器的形狀 | 驗證邊的兩端、算 `meta`（build 的事） |
| 定義產生器拿得到哪些背景知識（`Context`） | 讀檔、走訪目錄（scan 與呼叫端的事） |

> **加一種 Fact ＝ 表加一筆 ＋ 寫一個產生器。** `pipeline.py` 與 `build.py` 都不必動。

這句話是這一層存在的全部理由。分流曾經是 `pipeline.py` 裡誠實寫死的兩段；`Inherits`（5.4）進來時**那個檔案一行都沒改**，`Calls`（5.6）也會是同樣的走法。

---

## 2. 介面

### 2.1 契約 · `production.py`

| 名稱 | 形狀 |
|---|---|
| `Context` | frozen dataclass：`index: ModuleIndex`、`language: Language`、`names: NameIndex` |
| `Production` | frozen dataclass：`nodes: tuple[Node, ...] = ()`、`edges: tuple[Edge, ...] = ()`、`counters: Mapping[str, int] = {}` |
| `Producer` | Protocol：`produce(facts: Mapping[str, Sequence[Any]], context: Context) -> Production` |

`facts` 以**來源檔案的節點 id** 為 key——fact 自己不知道它從哪個檔案來。

`Context` 裝的是產生器可能要用到的**專案知識**（有哪些檔案、有哪些宣告）與**語言知識**（這個語言的名字怎麼解析），全部以參數傳入，不做成可變的全域狀態（同 `parse.md` §2.3）。

`names` 雖然是宣告事實的產物，**卻不是別的產生器的輸出**：它由 resolve 從同一份事實建好再放進 `Context`，所以 `to_graph` 仍然是平的，產生器彼此互不相識——§9 預告的走法就是這個。

`Producer` 的元素型別是 `Any`：表是異質的，各產生器在自己的簽章上寫清楚它吃 `Defines` 還是 `Import`。

### 2.2 表與迴圈 · `producers.py`

| 名稱 | 簽章 |
|---|---|
| `PRODUCERS` | `dict[type, Producer]` = `{Defines: DeclarationProducer(), Import: ImportProducer(), Inherits: InheritsProducer()}` |
| `to_graph` | `(facts: Mapping[str, Sequence[Fact]], context: Context, producers: Mapping[type, Producer] = PRODUCERS) -> Production` |
| `UnknownFactError` | `Exception` |

`producers` 收成參數是為了測試餵得進一張假表；正式路徑一律用預設的那張。

### 2.3 宣告產生器 · `declarations.py`

| 名稱 | 簽章 |
|---|---|
| `DeclarationProducer` | `produce(facts: Mapping[str, Sequence[Defines]], context: Context) -> Production` |
| `to_nodes` | `(facts: Mapping[str, Sequence[Defines]]) -> Production` |

**不查任何索引**，`Context` 收下了也用不到——宣告自己就是節點。所以這裡是純對應層，餵一份假 fact 就測得動。

`Production.counters` 恆為空：宣告不需要解析，抽得到就是對的。檔案整份解析失敗由 `meta.parse_failures` 涵蓋。

### 2.4 引用產生器 · `imports.py`

| 名稱 | 簽章 |
|---|---|
| `ImportProducer` | `produce(facts: Mapping[str, Sequence[Import]], context: Context) -> Production` |

薄殼：呼叫 `resolve.to_edges(facts, context.index, context.language.resolver)`，把 `ResolveResult` 的 `ambiguous` / `unresolved` 換成 `counters`。**名稱解析的演算法全部在 `app/resolve/`**，見 `resolve.md`。

### 2.5 繼承產生器 · `inherits.py`

| 名稱 | 簽章 |
|---|---|
| `InheritsProducer` | `produce(facts: Mapping[str, Sequence[Inherits]], context: Context) -> Production` |

同樣是薄殼：查 `context.names`，查到的接成邊。查表的演算法在 `resolve/names.py`（§3.6、§3.7），這裡只管邊長什麼樣。

**只回邊，不回節點**——兩端都是 `DeclarationProducer` 從同一批 `Defines` 事實產出來的 `class` 節點。這也是為什麼「解不到的 base」不能記在子類別節點的 `properties` 上：一個節點只能有一個產生器，兩個都產就會撞 id（`graph.md` B1），所以那筆資訊只剩計數。

---

## 3. 行為

### 3.1 分派 · `to_graph`

| # | 規則 |
|---|---|
| F1 | 依 `type(fact)` 把事實分堆，翻成「型別 → 檔案 → 這一種事實」。檔案的順序取 `sorted()`。 |
| F2 | 每一堆查 `producers`，交給查到的那個產生器。 |
| F3 | 有任何一種型別**查不到產生器**就丟 `UnknownFactError`，一次列出全部，不靜靜跳過。理由見 §8.1。 |
| F4 | 產生器依**表的順序**呼叫，不是依事實出現的順序。理由見 §8.2。 |
| F5 | 表上有、但這次一筆都沒有的型別**不呼叫**，不是傳空字典進去。 |
| F6 | 合併：節點與邊依序串接，`counters` 同名相加（`collections.Counter`）。 |

### 3.2 宣告 → 節點與邊 · `to_nodes`

| # | 規則 |
|---|---|
| D1 | 每一筆 `Defines` 產生一個節點，id 是 `make_id(kind, 檔案路徑, member=完整路徑)`，如 `function:src/app.py::Runner.run`。 |
| D2 | 每個節點一條 `defines` 邊：頂層宣告的來源是該 `file` 節點，其餘是包住它的那個宣告。 |
| D3 | 節點的 `label` 是**裸名**（`run`），完整路徑在 id 裡；`properties["line"]` 是宣告那一行。 |
| D4 | 同一個 id 只留一個節點，挑**第一筆 `overload=False`** 的；整組都是 `@overload` 簽章就挑第一筆。 |
| D5 | 被 D4 合併掉的那幾筆的行號記在 `properties["redefined_at"]`，資訊不丟。 |
| D6 | `defines` 邊的 `properties` 是空的——行號在節點上，邊再放一份是重複。 |

**D4 決定「能不能分析真實專案」。** Python 允許同一個作用域內同名（`@overload`、
`@property` 配 `.setter`、`if` 兩個分支各定義一次），而 `graph.md` B1 對重複的 id
直接丟 `BuildError`——不去重就是整次分析零結果。

實測（環境內裝好的套件，排除測試檔）：

| 套件 | 宣告數 | 撞名 | 主因 |
|---|---|---|---|
| pydantic | 2298 | **103（4.5%）** | `@overload` 84、條件式 19 |
| anyio | 1292 | **95（7.4%）** | `@overload` 62、條件式 21、setter 12 |
| networkx | 2329 | 39（1.7%） | 條件式 37、setter 2 |
| starlette | 574 | 9（1.6%） | `@overload` 9 |
| fastapi | 502 | 0 | — |

**挑哪一筆不能固定位置**：58 個 `@overload` 群組的實作**全部在最後一筆**（挑第
一筆會讓行號指到 `...` 空殼），而 14 個 `@property` 群組的**第一筆就是 getter**。
「第一筆非 overload」同時滿足兩者。

### 3.3 引用 → 邊與外部套件節點 · `ImportProducer`

| # | 規則 |
|---|---|
| F7 | 原樣轉交 `resolve.to_edges()`，不改它的輸入也不改它的輸出。 |
| F8 | `counters` 恆有兩個 key：`ambiguous_imports`、`unresolved_imports`，即使是 0。 |

### 3.4 繼承 → 邊 · `InheritsProducer`

| # | 規則 |
|---|---|
| H1 | 每一筆 `Inherits` 查一次 `context.names.lookup(檔案, base)`。 |
| H2 | 查到的**必須是 `class`**；查不到、或查到的是函式，都不產生邊。繼承只能是 class → class。 |
| H3 | 邊的 `properties` 有兩個：`base`（原始碼寫的樣子）與 `line`。target 的 id 是解析出來的結果，兩個擺在一起才看得出接對沒有。 |
| H4 | 沒有產生邊的筆數計進 `unresolved_inherits`，`counters` 恆有這個 key，即使是 0。 |

**H4 那個數字裡大部分是 builtins 與外部套件**（`Exception`、`BaseModel`），那是預期的，不是錯誤——實測本專案 13 筆全部如此。它與 `unresolved_imports` 的「接不到目標」性質不同，三分類（專案內／確定外部／真的不知道）是 plan 5.7 的事。

---

## 4. 產出的資料

| 產出 | 誰產的 | 說明 |
|---|---|---|
| `class` / `function` 節點 | `DeclarationProducer` | `properties` 有 `line`，被 D4 合併時多一個 `redefined_at` |
| `defines` 邊 | `DeclarationProducer` | `properties` 恆空（D6） |
| `imports` 邊、`external_package` 節點 | `ImportProducer` | 形狀見 `resolve.md` §4 |
| `inherits` 邊 | `InheritsProducer` | `properties` 有 `base` 與 `line`（H3）。**不產生節點** |
| `counters` | 各產生器 | **key 就是 `Diagnostics` 的欄位名**，見 §8.3 |

產生器**同時回節點與邊**，不是只回邊：`Import` 對不到專案內的檔案時要順手造出 `external_package` 節點，只回邊的話那條邊會指向不存在的節點，被 `graph.md` B2 擋下來。

---

## 5. 錯誤與邊界情況

| 情況 | 行為 |
|---|---|
| 某種 Fact 沒有註冊產生器 | `UnknownFactError`，一次列出全部型別名 |
| `facts` 是空的 | 回 `Production()`，不呼叫任何產生器 |
| 某個檔案有 fact 清單但內容是空的 | 該檔案不出現在任何一堆裡，等同沒有 |
| 表上某個型別這次沒有事實 | 不呼叫那個產生器（F5） |
| 產生器吐出 `Diagnostics` 沒有的 counter 名 | `pipeline.py` 的 `Diagnostics(**counts)` 直接丟 `TypeError`。**刻意不防**，見 §9 |
| 某個檔案 id 不是 `file:` 開頭 | `to_nodes` 丟 `ValueError`——那代表呼叫端交錯了 key |

---

## 6. 不變式

| # | 保證 |
|---|---|
| I1 | 每個產生器只看得到**自己負責的那一種型別**，所以它內部不必再寫 `isinstance`。 |
| I2 | 同一份 `facts` 跑兩次，`Production` 完全相同（F1 的 `sorted()` ＋ F4 的表順序）。 |
| I3 | 輸出的節點順序**不隨原始碼裡先寫 import 還是先寫 class 而變**（F4）。 |
| I4 | `to_graph` 不改動輸入的 `facts`，也不改動 `Context`（純函式，Fact 是 frozen）。 |
| I5 | 這一層不認識 `Diagnostics`、不認識 HTTP、不碰檔案系統。 |

---

## 7. 驗證

| 測試檔 | 筆數 | 涵蓋 |
|---|---|---|
| `tests/test_facts_producers.py` | 6 | F1–F8、I1–I3 |
| `tests/test_facts_declarations.py` | 12 | D1–D6 |
| `tests/test_facts_inherits.py` | 7 | H1–H4、跨檔案與巢狀的 id 形狀 |

`test_facts_producers.py` 的第一條是**完成條件本身**：測試裡自己定義一個 `app/` 完全不認識的 Fact 型別與它的產生器，用 `to_graph(facts, context, producers={Mentions: MentionProducer()})` 跑一次就出得了節點與邊——`pipeline.py` 與 `build.py` 一行都沒改。

### 搬進來時的回歸驗證（plan 5.2）

分流從 `pipeline.py` 搬到這裡是**純重構**，產出必須一個 byte 都不差。驗法是同一棵樹（`git worktree` 出一份 HEAD）餵給新舊兩份程式碼，比對 `document()` 的 JSON：8158 行完全相同。

---

## 8. 附錄：設計理由

### 8.1 為什麼查不到產生器要丟例外（F3）

跟「副檔名查不到 parser」看似同一件事，其實相反：

| | 查不到時 | 為什麼 |
|---|---|---|
| 副檔名 → parser | 跳過，**不是錯誤** | `README.md` 本來就不該 parse，它照樣有 `file` 節點 |
| Fact 型別 → 產生器 | **丟例外** | parser 吐得出這種事實，代表有人刻意加了它；沒人接就是表漏了一筆 |

靜靜跳過的後果是圖裡少一整批節點而沒有任何跡象——正是這個專案最該防的那種靜默失敗（同 `parse.md` §8.1 對正規掃描的評語）。

### 8.2 為什麼依表的順序跑（F4）

依事實出現的順序跑的話，「某個檔案先寫 `import` 還是先寫 `class`」會改變輸出陣列裡節點的先後。那不影響圖的內容，卻讓同一個專案的兩次分析產出不同的 JSON，diff 不動——與 `scan` 每層 `sorted()`、`graph.md` M3 旋轉 cycle 起點是同一個理由。

### 8.3 為什麼 `counters` 的 key 是 `Diagnostics` 的欄位名

三個計數要進 `meta`，而 `meta` 是前後端契約的一部分（`graph_schema.md`）。可能的做法有兩種：

| 做法 | 代價 |
|---|---|
| **約好用 `Diagnostics` 的欄位名**，pipeline 累加後 `Diagnostics(**counts)` | 名字沒有型別檢查，打錯要到執行期才知道（見 §9） |
| 把 `meta` 改成開放的 `{name: int}` 袋子 | 前後端契約變更：`Meta`、`types.ts`、前端讀計數的地方全都要改 |

選前者。這一層因此**不必 import `Diagnostics`**，`pipeline.py` 也不必提任何一個計數的名字——加一種計數只動產生器與 `Diagnostics`，中間那段是透明的。

### 8.4 為什麼自成一層，而不是放進 `app/graph/`

`declarations.py` 原本住在 `app/graph/`，因為 CLAUDE.md 把「`Fact → 節點/邊` 的對應規則」這條例外掛在 build 名下。表一旦成形，那個位置就站不住了：

| 放哪 | 代價 |
|---|---|
| `app/graph/` | `ImportProducer` 要呼叫 resolve，於是 build 那一層開始 import resolve——破掉「build 不在乎節點與邊從哪來」（`graph.md` §1） |
| `pipeline.py` | 加一種 Fact 又要動編排檔，等於沒解決原本的問題 |
| **`app/facts/`** | 與 `parsers/`、`resolve/`、`graph/` 並列 |

理由與 `app/languages/` 獨立成一層完全相同（`System_arch.md`）：**需要同時認得上下游的那個接線點，自己要有一層**。這一層認得 `parsers`（吃 Fact）、`resolve`（查名字）與 `models`（吐節點），而它們三者都不認得它。

### 8.5 為什麼契約另開一個檔（`production.py`）

`producers.py` 要 import 兩個產生器來組表，兩個產生器又要 import `Context` 與 `Production` 當簽章——寫在同一個檔案就是循環 import。契約獨立成 `production.py` 之後，相依是單向的：

```
production.py  ←──  declarations.py  ←──┐
      ↑                                  producers.py
      └────────────  imports.py  ←──────┘
```

### 8.6 為什麼不是「Fact 自己宣告它產生什麼邊」

CLAUDE.md 與 `parse.md` §9 原本寫的是這個做法，**實作時發現做不到**，改成型別 → 產生器的表。兩個擋路的地方：

| 擋在哪 | 說明 |
|---|---|
| Fact 不知道自己的邊指向誰 | `Import("fastapi")` 在 resolve 之前不知道 target 是 `ext:fastapi` 還是某個 `file:` 節點。那正是 parse 與 resolve 的分界（`parse.md` §1），要 Fact 自己說等於把全域索引交給它 |
| 讓 Fact 宣告節點要破另一條界線 | 產生 `Node` 就得 `import app.models`，而「Fact 不是節點」與 `kind` 刻意用字串（`parse.md` §2.2、§8.5）都靠 parse 不認識 `app.models` 撐著 |

表把這兩件事都留在 parse 之外：**Fact 仍然只是資料，知道怎麼接圖的是產生器**。完成條件（「加一種 Fact 不必在 build 加一個 `if`」）一樣達成，代價只是多一個註冊動作。

---

## 9. 未定之處

| 項目 | 缺什麼 | 重新評估的時機 |
|---|---|---|
| `counters` 的名字沒有型別檢查 | 產生器吐出 `Diagnostics` 沒有的 key 時，要到 `pipeline.py` 組 `Diagnostics` 才炸。改成 enum 或 `TypedDict` 都能檢查，但也把這一層綁回 `Diagnostics` | 計數種類變多、或真的打錯過一次時 |
| 產生器之間的相依 | ~~預告的走法~~**已經驗證過**：5.4 的 `InheritsProducer` 要用「名字 → 宣告」表，做法是由 resolve 從同一份事實建好、放進 `Context`，`to_graph` 仍然是平的。`Calls`（5.6）照同一條路，但它還要作用域感知（5.5） | 5.6 開工時只剩「表夠不夠用」要評估，走法不必再討論 |
| 一種 Fact 對多個產生器 | 表是一對一。若某種 Fact 之後要同時產生兩類東西，得改成一對多 | 真的出現時 |
