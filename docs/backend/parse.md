# parse 規格

對應程式碼 `backend/app/parsers/`（語言 registry 在 `backend/app/languages/`）。職責的位置定義在 CLAUDE.md › 架構 › parse。

---

## 1. 職責

把**單一檔案的內容**變成**帶型別的事實**。

| 做 | 不做 |
|---|---|
| 抽出這個檔案裡的事實 | 判斷那個名字指向誰（resolve 的事） |
| 回報相對 import 的層數 | 把層數換算成路徑（resolve 的事） |
| 回報解析失敗 | 決定失敗要怎麼呈現（前端的事） |
| 讀一段字串 | 開檔、走訪目錄（scan／呼叫端的事） |

**兩個刻意的限制**：

| 限制 | 換來 |
|---|---|
| 只看單一檔案、沒有全域視野（抽到 `"fastapi"` 時並不知道那是外部套件） | parser 能用字串單獨測試，不必準備假專案 |
| 完全不做路徑解析（即使看得出是相對 import 也只回報層數） | 「名字指向誰」集中在 resolve 一處，不散落到每個語言 |

---

## 2. 介面

### 2.1 協定

```python
class Parser(Protocol):
    def parse(self, source: str) -> ParseResult: ...
```

**吃字串，不吃路徑。** parser 不碰檔案系統，讀檔是呼叫端的事。

### 2.2 型別

| 型別 | 欄位 | 型別 | 意義 |
|---|---|---|---|
| `Import` | `module` | `str \| None` | 先去找哪個模組。`from . import x` 為 `None` |
| | `level` | `int` | 0 = 絕對，1 = 同層，2 = 上一層 |
| | `name` | `str \| None` | 從 `module` 裡取出的名字。整包 `import x` 為 `None` |
| | `alias` | `str \| None` | `as` 後面的別名 |
| | `line` | `int` | 在原始碼的第幾行 |
| `ParseResult` | `facts` | `tuple[Fact, ...]` | 預設 `()` |
| | `error` | `str \| None` | 預設 `None` |
| `Fact` | — | `= Import` | union 別名。之後：`Import \| Defines \| Calls \| Inherits` |

全部為 `@dataclass(frozen=True)`，**不是 pydantic**。理由見 §8.4。

### 2.3 語言 registry

parse 與 resolve **共用同一份**，以副檔名為 key，一筆同時掛兩者。

| 名稱 | 簽章 | 說明 |
|---|---|---|
| `LANGUAGES` | `dict[str, Language]` | `{".py": Language(parser=PythonParser(), resolver=PythonResolver())}` |
| `Language` | frozen dataclass | 欄位 `parser: Parser`、`resolver: Resolver` |
| `for_path` | `(path: str) -> Language \| None` | 副檔名查不到回 `None` |

**新增語言 ＝ 這張表加一筆**，parse 與 resolve 的程式碼都不動。合成一筆而不是兩張表，是為了不可能只加一半（parser 有、resolver 漏掉會變成解析得出結果卻接不到節點，而且不會報錯）。

registry 裝的是**語言知識**，對每個專案都一樣；**專案知識**（有哪些檔案）只有 resolve 拿得到，走參數傳入。兩者都不做成可變的全域狀態。

---

## 3. 行為

### 3.1 選 parser · `for_path`

| # | 規則 |
|---|---|
| R1 | 以副檔名查 `LANGUAGES`，查不到回 `None`。 |
| R2 | 沒有 `.` 的檔名（`Makefile`）一律回 `None`。 |
| R3 | 查不到**不是錯誤**：那個檔案仍有 `file` 節點，只是不 parse。 |

### 3.2 抽 import · `PythonParser.parse`

| # | 規則 |
|---|---|
| R4 | 用標準庫 `ast.parse()`。定案理由見 §8.1。 |
| R5 | 走**整棵樹**（`ast.walk`），不只看頂層——`if TYPE_CHECKING:` 內與函式內的 import 都算。 |
| R6 | `ast.Import` 的每個 alias 各產生一筆：`module=alias.name`、`level=0`、`name=None`、`alias=alias.asname`。 |
| R7 | `ast.ImportFrom` 的每個 alias 各產生一筆：`module=node.module`、`level=node.level`、`name=alias.name`、`alias=alias.asname`。 |
| R8 | `line` 取該 import 敘述的 `lineno`，同一句跨行時是**起始行**。 |
| R9 | 回傳前依 `line` 排序。排序穩定，所以同一行內的多個名字維持原順序。 |

`module` 與 `name` 的分工是：**`module` 是「先去找哪個模組」，`name` 是「從它裡面拿了什麼」**。

| 原始碼 | `module` | `level` | `name` | `alias` |
|---|---|---|---|---|
| `import a.b.c as abc` | `"a.b.c"` | 0 | `None` | `"abc"` |
| `from foo import bar` | `"foo"` | 0 | `"bar"` | `None` |
| `from . import sibling` | `None` | 1 | `"sibling"` | `None` |
| `from ..pkg import deep` | `"pkg"` | 2 | `"deep"` | `None` |

這讓 resolve 的第一步永遠是同一件事：拿 `module` ＋ `level` 去找檔案。

### 3.3 失敗處理

| # | 規則 |
|---|---|
| R10 | 失敗**回結果物件，不拋例外**：`ParseResult(error=...)`，`facts` 為空。 |
| R11 | `SyntaxError` 的訊息組成 `"{msg} (line {lineno})"`；沒有 `lineno` 時只有 `msg`。 |
| R12 | `ValueError`（副檔名是 `.py` 但內容含空位元組）同樣當解析失敗，訊息取 `str(error)`。 |
| R13 | 失敗即**整份檔案歸零**，一個 import 都拿不到。這是 `ast` 的性質，不是可調整的行為。 |

---

## 4. 產出的資料

### 4.1 交給 resolve

`ParseResult.facts`。Fact **不是節點，也不是邊**：

```
parse    →  Fact   「這個檔案第 11 行寫了 from app.graph import build」
                    （還不知道 app.graph 是誰）
resolve  →  Edge   「file:app/api/analyze.py --imports--> file:app/graph/__init__.py」
```

### 4.2 失敗的痕跡

失敗一律留下痕跡，兩個層次：

| 層次 | 放哪 | 回答什麼問題 |
|---|---|---|
| 個別檔案 | 該 `file` 節點的 `properties["parse_error"]`，值是錯誤訊息 | **是哪些檔案** |
| 全域 | `meta.parse_failures`，一個數字 | **有多嚴重** |

```json
{ "id": "file:src/broken.py", "type": "file", "label": "broken.py",
  "properties": { "parse_error": "invalid syntax (line 12)" } }
```

貼到節點與計數都由管線做（`pipeline.py` 的 `_annotated()` 與 `Diagnostics`），不是 parser 自己做——parser 沒有節點可以改，管線是單向的。

**不開新的節點型別。** 解析失敗的檔案仍然是 `file`。判準：

> **`type` 說「這是什麼」，`properties` 說「我們對它知道多少」。**

---

## 5. 錯誤與邊界情況

| 情況 | 行為 | 算 `parse_failures` 嗎 |
|---|---|---|
| 語法錯誤 | `ParseResult(error=...)`，整份歸零 | **算** |
| 用了比後端 Python 版本更新的語法 | 同上（`SyntaxError`） | **算** |
| 副檔名是 `.py` 但內容是二進位 | 同上（`ValueError`） | **算** |
| `README.md`、`.png` | 根本不送進 parse（R1） | **不算** |
| `.py` 但整份沒有任何 import | `facts=()` 且 `error is None` | **不算** |
| 動態 import（`__import__`、`importlib.import_module`） | 抽不到，無聲無息 | **不算** |

最後三種**都不是失敗**，混進同一個數字會讓那個數字失去意義。「沒有 import」與「解析失敗」的差別就在 `error` 是不是 `None`。

### 語法上限

**後端的 Python 版本 ＝ 能解析的語法上限。** 後端目前是 3.11：

| 語法 | 3.11 解析 |
|---|---|
| `match x: case 1:`（3.10） | 成功 |
| `type Alias = int`（3.12） | **SyntaxError** |
| `def f[T](x: T) -> T:`（3.12 泛型） | **SyntaxError** |

要分析用 3.12 寫的專案，**先升後端的 Python**，而不是急著換 parser。

---

## 6. 不變式

| # | 保證 |
|---|---|
| I1 | `error` 不為 `None` 時，`facts` 必然為空。 |
| I2 | 同一段原始碼解析兩次，`ParseResult` 完全相同（R9）。 |
| I3 | parser 不讀檔案系統、不做網路存取、不改任何外部狀態。 |
| I4 | Fact 是 frozen，resolve 不能偷改 parse 給的東西。 |
| I5 | 註解與字串裡的假 import **不會**被抽出來（R4 的直接後果）。 |

---

## 7. 驗證

| 測試檔 | 筆數 | 涵蓋 |
|---|---|---|
| `tests/test_parsers_python.py` | 12 | R4–R13、I1、I5、四種 `module`/`name` 組合 |

實測（同一段刁鑽的程式碼，全對）：

| 原始碼 | `ast` 抽到 |
|---|---|
| `from foo import (bar,\n baz)` | 兩筆，`module='foo'` `level=0` |
| `import a.b.c as abc` | `module='a.b.c'` `alias='abc'` |
| `from . import sibling` | `module=None` **`level=1`** |
| `from ..pkg import deep` | `module='pkg'` **`level=2`** |
| `if TYPE_CHECKING:` 內的 import | 有抓到 |
| 函式內的 import | 有抓到 |
| 註解與字串裡的假 import | **沒有誤抓** |

---

## 8. 附錄：設計理由

### 8.1 為什麼 Python 用 `ast`（R4）

CLAUDE.md 原本把三種技術都列為候選，這裡定案。

| 基準 | 正規掃描 | **`ast`** | tree-sitter |
|---|---|---|---|
| 抽 import 的正確性 | 會漏也會誤抓 | 全對 | 全對 |
| 相對 import 的層數 | 自己數點 | **現成的 `level` 欄位** | 自己看樹 |
| 行號 | 勉強 | 有 | 有 |
| 新增依賴 | 0 | **0** | 2（`tree-sitter` ＋ grammar） |
| 語法錯誤的檔案 | 照常運作 | **整份歸零** | 仍抽得到 |
| 比自己新的語法 | 照常運作 | **整份歸零** | 部分節點變 `ERROR`，其餘照抽 |
| 多語言共用 | 不可能 | 只能 Python | 唯一的優勢 |

**淘汰正規掃描**：它會同時漏抓與誤抓，而且都是靜默的。

```python
from foo import (bar,          # 括號跨行 → 漏掉 baz
                 baz)
# import fake_comment          # 註解   → 誤抓
sql = "import fake_string"     # 字串   → 誤抓
```

誤抓比漏抓更糟：resolve 對不到 `fake_comment`，會忠實地造一個 `ext:fake_comment` 節點，圖上多一個不存在的套件，而且看起來很正常。這個專案的核心價值是圖的正確性，這條路從根上放棄它。

**不選 tree-sitter**：它值錢的地方有兩個，現在都不值錢。

| 優勢 | 現在值多少 |
|---|---|
| 容錯解析 | 有價值，但 §4.2 的顯性回報是更便宜的緩解方式 |
| 多語言統一 | **0**。階段 2 只做 Python |
| 增量解析 | 0。每個檔案只解析一次 |

而 `ast` 額外給了一件 tree-sitter 沒有的：它輸出的是**語意層**的結果（`level=2` 直接是數字），tree-sitter 給的是語法層（要自己數 `.` 的節點）。

**registry 讓這一票只綁 Python。** 之後加 TS 時，`.ts` 那筆可以掛 tree-sitter 的 parser，`.py` 這筆不動。統一解析技術從來不是目標。

### 8.2 何時該改用 tree-sitter

寫下觸發條件，之後不必重新討論：

- 要加第二個語言，且該語言沒有堪用的原生 parser；或
- 跑真實專案時 `meta.parse_failures` 大到會影響結論。

換掉的成本是 registry 一筆，其他層不動。

### 8.3 為什麼裸字串不夠

resolve 需要的資訊，字串裡塞不下：

| 原始碼 | 裸字串 | 遺失 | 後果 |
|---|---|---|---|
| `from . import sibling` | `"sibling"` | `level=1` | 不知道從哪個資料夾開始找 |
| `from ..pkg import deep` | `"pkg.deep"` | `level=2` | 會被誤當成絕對 import |
| `import a.b.c as abc` | `"a.b.c"` | `alias` | 第二階段接 `calls` 時需要 |
| 任何 import | — | 行號 | `properties` 想放行號沒得放 |

### 8.4 為什麼是 dataclass 而不是 pydantic

除了輕，還建立一條分界線：

> **用不用 pydantic，標示「這個型別會不會跨邊界」。**

`app/models/` 的東西要變成 JSON 給前端，pydantic 在那裡是對的。Fact 從頭到尾活在 parse → resolve 之間，不落地、不上線、不需要驗證外來輸入。`frozen` 則是為了 I4。

### 8.5 為什麼 Fact 用真型別，圖模型卻用字串 `type`

看似矛盾，但兩者受的力不同：

| | 圖模型的 `Node.type` | Fact |
|---|---|---|
| 誰讀 | 前端、序列化——**不關心是哪一種**，一律當資料跑迴圈 | resolve、build——**必須分辨**，`Import` 要查全域索引，`Defines` 直接變節點 |
| 所以 | 型別當字串資料 | 型別當真的型別 |

強行讓 Fact 也「型別是資料」，只是把 `isinstance` 換成 `if fact.kind == "import"`，一樣要分流，還少了型別檢查。

同理，型別怎麼分辨用**各自一個 class ＋ union 別名**：欄位各自剛好；單一 class 加 `kind` 會逼出一堆 `Optional`，而且 mypy 幫不上忙。

### 8.6 為什麼失敗不拋例外（R10）

兩個理由：

1. 拋例外會讓「跳過」變成預設行為，少寫一行 `except` 就是靜默失敗——那正是選 `ast` 最需要防的風險。
2. `error` 字串要一路流到節點的 `properties`，拋例外就在呼叫端丟掉了。

### 8.7 為什麼保留 `name`（R7）

`from foo import bar` 的 `bar` 可能是 `foo/bar.py`（一個模組），也可能是 `foo/__init__.py` 裡的一個函式。**parser 看不出來，這正是 parse 與 resolve 的分界**：忠實記下兩者，讓 resolve 兩種都試（見 `resolve.md` R5）。

### 8.8 其他自行決定的部分

| 決定 | 理由 | 推翻的代價 |
|---|---|---|
| `Import` 的欄位取這五個 | 對齊 `ast.Import` / `ast.ImportFrom` 實際給得出的東西，不多包裝 | 改 dataclass 與 parser |
| `ParseResult.error` 是字串不是例外物件 | 它要進 JSON 給前端看，例外物件序列化不了 | 改型別 |
| `properties` 的鍵名叫 `parse_error` | `properties` 的鍵沒有全域約定（見 `graph_schema.md` §9） | 改一處 pipeline 端、一處 `style.ts` |
| `name` 在整包 `import x` 時為 `None`，而非重複填 `module` | 「沒有從裡面取出東西」與「取出了同名的東西」是不同的事 | 改 dataclass 與 parser |
| 二進位內容也當解析失敗（R12） | 同樣是「這個檔案有問題」，不是我們的 bug，不該讓整次分析崩掉 | 改 parser 的 `except` |
| 事實依行號排序（R9） | `ast.walk` 是廣度優先，順序與原始碼無關 | 拿掉 `sorted` |
| 動態 import 不計入失敗 | 那不是失敗，是靜態分析的邊界 | — |

---

## 9. 未定之處

| 主題 | 未定的事 | 重新評估的時機 |
|---|---|---|
| Fact 宣告邊 | Fact 要不要自己說明它產生什麼節點／邊，好讓 build 變成不認識具體型別的通用迴圈。現在 build 仍需一條 `Fact → 節點/邊` 的對應規則，是 CLAUDE.md 承認的唯一例外 | **第三種 Fact 出現時**。階段 2 只有 `Import` 一種，用一個實例設計通用機制幾乎必定設計錯。而且就算 build 通用化，resolve 仍要分流（`Import` 是「模組名 → 檔案」、`Calls` 是「函式名 → 函式」，兩套演算法），最多只清掉一層 |
| 語法上限的記錄 | 是否要在 `meta` 記下後端的 Python 版本，讓「為什麼這些檔案失敗」有跡可循 | 真的遇到版本落差時 |
| 動態 import | 目前完全看不到。要不要至少標記「這個檔案有動態 import」尚未決定 | 遇到大量使用的專案時 |
