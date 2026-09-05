# parse 層的實作決定

parse 把**單一檔案的內容**變成**帶型別的事實**。職責定義在 CLAUDE.md › 架構 › parse，這份文件談的是實作決定：用什麼技術解析、事實長什麼形狀、失敗了怎麼辦。

對應程式碼 `backend/app/parsers/`。

---

## 解析技術：Python 用 `ast`

CLAUDE.md 原本把三種技術都列為候選。這裡定案：**Python 走標準庫的 `ast`**。

### 三案比較

| 基準 | 正規掃描 | **`ast`** | tree-sitter |
|---|---|---|---|
| 抽 import 的正確性 | 會漏也會誤抓 | 全對 | 全對 |
| 相對 import 的層數 | 自己數點 | **現成的 `level` 欄位** | 自己看樹 |
| 行號 | 勉強 | 有 | 有 |
| 新增依賴 | 0 | **0** | 2（`tree-sitter` ＋ grammar） |
| 語法錯誤的檔案 | 照常運作 | **整份歸零** | 仍抽得到 |
| 比自己新的語法 | 照常運作 | **整份歸零** | 部分節點變 `ERROR`，其餘照抽 |
| 多語言共用 | 不可能 | 只能 Python | 唯一的優勢 |

### 為什麼淘汰正規掃描

它會**同時**漏抓與誤抓，而且都是靜默的：

```python
from foo import (bar,          # 括號跨行 → 漏掉 baz
                 baz)
# import fake_comment          # 註解   → 誤抓
sql = "import fake_string"     # 字串   → 誤抓
```

誤抓比漏抓更糟：resolve 對不到 `fake_comment`，會忠實地造一個 `ext:fake_comment` 節點，圖上多一個不存在的套件，而且看起來很正常。這個專案的核心價值是圖的正確性，這條路從根上放棄它。

### `ast` 的實測結果

同一段刁鑽的程式碼，全對：

| 原始碼 | `ast` 抽到 |
|---|---|
| `from foo import (bar,\n baz)` | 兩筆，`module='foo'` `level=0` |
| `import a.b.c as abc` | `name='a.b.c'` `asname='abc'` |
| `from . import sibling` | `module=None` **`level=1`** |
| `from ..pkg import deep` | `module='pkg'` **`level=2`** |
| `if TYPE_CHECKING:` 內的 import | 有抓到 |
| 函式內的 import | 有抓到 |
| 註解與字串裡的假 import | **沒有誤抓** |

`level` 是關鍵。`from . import sibling` 與 `from sibling import x` 用字串表達會撞在一起，但它們指向完全不同的檔案——resolve 需要這個數字才接得對。

### 為什麼不是 tree-sitter

它值錢的地方有兩個：容錯解析、一套 API 吃多語言。

| 優勢 | 現在值多少 |
|---|---|
| 容錯解析 | 有價值，但見下方「限制與對策」——可以用更便宜的方式緩解 |
| 多語言統一 | **0**。階段 2 只做 Python |
| 增量解析 | 0。每個檔案只解析一次 |

而 `ast` 額外給了一件 tree-sitter 沒有的：它輸出的是**語意層**的結果（`level=2` 直接是數字），tree-sitter 給的是語法層（要自己數 `.` 的節點）。

**registry 讓這一票只綁 Python。** 之後加 TS 時，`.ts` 那筆可以掛 tree-sitter 的 parser，`.py` 這筆不動。統一解析技術從來不是目標。

---

## `ast` 的兩個限制與對策

### 限制一：語法錯誤 → 整份檔案歸零

```
ast.parse("def broken(:")  →  SyntaxError
```

不是「抓到一半」，是這個檔案**一個 import 都拿不到**。

### 限制二：只認得自己版本以前的語法

後端目前是 Python 3.11.16，實測：

| 語法 | 3.11 解析 |
|---|---|
| `match x: case 1:`（3.10） | 成功 |
| `type Alias = int`（3.12） | **SyntaxError** |
| `def f[T](x: T) -> T:`（3.12 泛型） | **SyntaxError** |

**後端的 Python 版本＝能解析的語法上限。** 要分析用 3.12 寫的專案，先升後端的 Python，而不是急著換 parser。

### 對策：讓失敗顯性化

兩個限制的共同危險是**靜默**——圖少了邊，畫面上看不出來。所以失敗一律留下痕跡，兩個層次：

| 層次 | 放哪 | 回答什麼問題 |
|---|---|---|
| 個別檔案 | 該 `file` 節點的 `properties["parse_error"]`，值是錯誤訊息 | **是哪些檔案** |
| 全域 | `meta.parse_failures`，一個數字 | **有多嚴重** |

```json
{ "id": "file:src/broken.py", "type": "file", "label": "broken.py",
  "properties": { "parse_error": "invalid syntax (line 12)" } }
```

**不開新的節點型別。** 解析失敗的檔案仍然是 `file`——它還是一個檔案，只是我們對它多知道一件事。開一個 `unparsed_file` 型別會讓所有篩 `type = "file"` 的地方漏掉它。

> 判準：**`type` 說「這是什麼」，`properties` 說「我們對它知道多少」。**

視覺呈現屬前端，寫在 `Frontend.md`；資料面的約定就是 `parse_error` 這個鍵名。

### 要分清楚的兩件事

| 情況 | 算失敗嗎 |
|---|---|
| `README.md`、`.png` | **不算**。registry 查不到副檔名，根本不送進 parse。「進圖但不 parse」是正常的 |
| `.py` 但解析不了 | **算**，要計數並標記 |

混進同一個數字會讓那個數字失去意義。

### 何時該改用 tree-sitter

寫下觸發條件，之後不必重新討論：

- 要加第二個語言，且該語言沒有堪用的原生 parser；或
- 跑真實專案時 `meta.parse_failures` 大到會影響結論。

換掉的成本是 registry 一筆，其他層不動。

---

## 三案共同的限制：動態 import

```python
__import__("dynamic")
importlib.import_module("also_dynamic")
```

這兩種**任何靜態分析都抽不到**，`ast` 抽不到、tree-sitter 也抽不到，因為模組名要執行才知道。不是選型問題，是靜態分析的邊界。目前不處理，也不計入失敗。

---

## Fact：parse 交出去的形狀

CLAUDE.md 規定 parse 回「帶型別的事實」而非裸字串。這裡定實作。

### 為什麼裸字串不夠

resolve 需要的資訊，字串裡塞不下：

| 原始碼 | 裸字串 | 遺失 | 後果 |
|---|---|---|---|
| `from . import sibling` | `"sibling"` | `level=1` | 不知道從哪個資料夾開始找 |
| `from ..pkg import deep` | `"pkg.deep"` | `level=2` | 會被誤當成絕對 import |
| `import a.b.c as abc` | `"a.b.c"` | `alias` | 第二階段接 `calls` 時需要 |
| 任何 import | — | 行號 | `properties` 想放行號沒得放 |

### Fact 不是節點，也不是邊

```
parse    →  Fact   「這個檔案第 11 行寫了 from app.graph import build」
                    （還不知道 app.graph 是誰）
resolve  →  Edge   「file:app/api/analyze.py --imports--> file:app/graph/__init__.py」
```

parser 抽到 `"fastapi"` 時**並不知道那是外部套件**——它沒有全域視野。Fact 是「還沒接上圖的半成品」。

### 四個決定

| 題 | 決定 | 理由 |
|---|---|---|
| 用什麼實作 | **`@dataclass(frozen=True)`** | 見下 |
| 型別怎麼分辨 | **各自一個 class**，用 union 別名收起來 | 欄位各自剛好；單一 class 加 `kind` 會逼出一堆 `Optional`，且 mypy 幫不上忙 |
| 失敗怎麼回報 | **回結果物件**，不拋例外 | 拋例外會讓「跳過」變成預設行為，少寫一行 `except` 就是靜默失敗。而且 `error` 字串要一路流到節點的 `properties`，拋例外就在呼叫端丟掉了 |
| Fact 要不要自己宣告產生什麼邊 | **先不做** | 見「未定之處」 |

**為什麼 dataclass 而不是 pydantic**——除了輕，還建立一條分界線：

> **用不用 pydantic，標示「這個型別會不會跨邊界」。**

`app/models/` 的東西要變成 JSON 給前端，pydantic 在那裡是對的。Fact 從頭到尾活在 parse → resolve 之間，不落地、不上線、不需要驗證外來輸入。`frozen` 則是為了 resolve 不能偷改 parse 給的東西。

### 為什麼 Fact 用真型別，圖模型卻用字串 `type`

看似矛盾，但兩者受的力不同：

| | 圖模型的 `Node.type` | Fact |
|---|---|---|
| 誰讀 | 前端、序列化——**不關心是哪一種**，一律當資料跑迴圈 | resolve、build——**必須分辨**，`Import` 要查全域索引，`Defines` 直接變節點 |
| 所以 | 型別當字串資料 | 型別當真的型別 |

強行讓 Fact 也「型別是資料」，只是把 `isinstance` 換成 `if fact.kind == "import"`，一樣要分流，還少了型別檢查。

### 形狀

```python
@dataclass(frozen=True)
class Import:
    module: str | None     # 要解析的模組路徑；from . import x 時為 None
    level: int             # 0=絕對，1=同層，2=上一層
    name: str | None       # 從 module 裡取出的名字；整包 import 時為 None
    alias: str | None
    line: int

Fact = Import              # 之後：Import | Defines | Calls | Inherits

@dataclass(frozen=True)
class ParseResult:
    facts: tuple[Fact, ...]
    error: str | None = None
```

`module` 與 `name` 的分工是：**`module` 是「先去找哪個模組」，`name` 是「從它裡面拿了什麼」**。

| 原始碼 | `module` | `level` | `name` | `alias` |
|---|---|---|---|---|
| `import a.b.c as abc` | `"a.b.c"` | 0 | `None` | `"abc"` |
| `from foo import bar` | `"foo"` | 0 | `"bar"` | `None` |
| `from . import sibling` | `None` | 1 | `"sibling"` | `None` |
| `from ..pkg import deep` | `"pkg"` | 2 | `"deep"` | `None` |

這讓 resolve 的第一步永遠是同一件事：拿 `module` ＋ `level` 去找檔案。

`name` 為什麼要留著——`from foo import bar` 的 `bar` 可能是 `foo/bar.py`（一個模組），也可能是 `foo/__init__.py` 裡的一個函式。**parser 看不出來，這正是 parse 與 resolve 的分界**：忠實記下兩者，讓 resolve 兩種都試。

parser 介面：

```python
class Parser(Protocol):
    def parse(self, source: str) -> ParseResult: ...
```

**吃字串，不吃路徑。** CLAUDE.md 要求的「餵一段程式碼字串、斷言吐出的 fact 清單」直接落在型別上——parser 不碰檔案系統，讀檔是呼叫端的事。

---

## 職責邊界

| 做 | 不做 |
|---|---|
| 抽出這個檔案裡的事實 | 判斷那個名字指向誰（resolve） |
| 回報相對 import 的層數 | 把層數換算成路徑（resolve） |
| 回報解析失敗 | 決定失敗要怎麼呈現（前端） |
| 讀一段字串 | 開檔、走訪目錄（scan／呼叫端） |

兩個刻意的限制換來的東西：

| 限制 | 換來 |
|---|---|
| 只看單一檔案、沒有全域視野 | parser 能用字串單獨測試，不必準備假專案 |
| 完全不做路徑解析 | 「名字指向誰」集中在 resolve 一處，不散落到每個語言 |

---

## 未定之處

| 主題 | 未定的事 | 重新評估的時機 |
|---|---|---|
| Fact 宣告邊 | Fact 要不要自己說明它產生什麼節點／邊，好讓 build 變成不認識具體型別的通用迴圈。現在 build 仍需一條 `Fact → 節點/邊` 的對應規則，是 CLAUDE.md 承認的唯一例外 | **第三種 Fact 出現時**。階段 2 只有 `Import` 一種，用一個實例設計通用機制幾乎必定設計錯。而且就算 build 通用化，resolve 仍要分流（`Import` 是「模組名 → 檔案」、`Calls` 是「函式名 → 函式」，兩套演算法），最多只清掉一層 |
| `parse_error` 貼到節點 | 誰負責合併。file 節點由 scan 產、error 由 parse 產，管線單向所以 parse 不能回頭改。傾向由 build 收一份 `{file_id: error}` 對照表——build 本來就是匯流點 | 寫 2.5 / build 接線時 |
| `meta.parse_failures` | `meta` 是固定欄位（pydantic 寫死），加這一個要同步改 `frontend/src/api/types.ts` | 實作時一起改 |
| 語法上限 | 是否要在 `meta` 記下後端的 Python 版本，讓「為什麼這些檔案失敗」有跡可循 | 真的遇到版本落差時 |

---

## 自行決定的部分

以下沒有上位依據，是定案時判斷的，要推翻只需改對應的一兩處。

| 決定 | 理由 | 推翻的代價 |
|---|---|---|
| `Import` 的欄位取這五個 | 對齊 `ast.Import` / `ast.ImportFrom` 實際給得出的東西，不多包裝 | 改 dataclass 與 parser |
| `ParseResult.error` 是字串不是例外物件 | 它要進 JSON 給前端看，例外物件序列化不了 | 改型別 |
| `properties` 的鍵名叫 `parse_error` | `properties` 的鍵沒有全域約定（見 `graph_schema.md` 的未定之處） | 改一處 parser 端、一處 `style.ts` |
| `name` 在整包 `import x` 時為 `None`，而非重複填 `module` | 「沒有從裡面取出東西」與「取出了同名的東西」是不同的事 | 改 dataclass 與 parser |
| 二進位內容（副檔名是 `.py` 但含空位元組）也當解析失敗 | `ast.parse` 對它拋的是 `ValueError` 不是 `SyntaxError`。同樣是「這個檔案有問題」，不是我們的 bug，不該讓整次分析崩掉 | 改 parser 的 except |
| 事實依行號排序後才回傳 | `ast.walk` 是廣度優先，順序與原始碼無關。排序是穩定的，所以同一行內的多個名字維持原順序 | 拿掉 `sorted` |
| 動態 import 不計入失敗 | 那不是失敗，是靜態分析的邊界 | — |
