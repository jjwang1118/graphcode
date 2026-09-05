"""parse 層交出去的形狀。

parse 回「帶型別的事實」而非裸字串：resolve 需要的 `level`、`alias`、行號都塞
不進字串，而 `from . import x` 與 `from x import y` 用字串表達會撞在一起。

**Fact 不是節點，也不是邊。** parser 沒有全域視野，抽到 "fastapi" 時並不知道
那是外部套件——要等 resolve 比對過全域索引才接得上圖。Fact 是還沒接上圖的半
成品。

用 dataclass 而非 pydantic 是刻意的：**用不用 pydantic 標示這個型別會不會跨邊
界**。Fact 從頭到尾活在 parse → resolve 之間，不落地也不上線。設計見
docs/backend/parse.md。
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Import:
    """一筆 import。

    `module` 是「先去找哪個模組」，`name` 是「從它裡面拿了什麼」：

    ==========================  =======  =====  =======  =====
    原始碼                      module   level  name     alias
    ==========================  =======  =====  =======  =====
    ``import a.b.c as abc``     a.b.c    0      None     abc
    ``from foo import bar``     foo      0      bar      None
    ``from . import sibling``   None     1      sibling  None
    ``from ..pkg import deep``  pkg      2      deep     None
    ==========================  =======  =====  =======  =====

    `name` 可能是子模組（``foo/bar.py``），也可能是 ``foo/__init__.py`` 裡的
    一個函式——parser 看不出來，兩種都記著讓 resolve 去試。這正是 parse 與
    resolve 的分界。
    """

    #: 要解析的模組路徑。``from . import x`` 沒有這一段，為 None
    module: str | None
    #: 相對層數。0 = 絕對 import，1 = 同層，2 = 上一層
    level: int
    #: 從 module 裡取出的名字。整包 ``import x`` 沒有這一段，為 None
    name: str | None
    #: ``as`` 後面的別名
    alias: str | None
    #: 這筆 import 在原始碼的第幾行
    line: int


#: parse 產出的事實。之後：Import | Defines | Calls | Inherits
Fact = Import


@dataclass(frozen=True)
class ParseResult:
    """一個檔案的解析結果。

    失敗**不拋例外**：`error` 要一路流到該 file 節點的 `properties`，拋例外會
    在呼叫端就被丟掉。而且例外會讓「跳過」變成預設行為，少寫一行 except 就是
    靜默失敗——那正是選 ast 最需要防的風險。

    沒有 import 與解析失敗是兩回事：前者 ``facts=()`` 而 ``error is None``。
    """

    facts: tuple[Fact, ...] = ()
    error: str | None = None


class Parser(Protocol):
    """吃字串，不吃路徑。

    parser 不碰檔案系統，讀檔是呼叫端的事——這樣才能用「餵一段程式碼字串、斷
    言吐出的 fact 清單」單獨測試，不必準備假專案。
    """

    def parse(self, source: str) -> ParseResult: ...
