"""名字表：這個檔案裡寫的一個名字，指向哪一個宣告。

`index.py` 那張表回答「模組名 → 哪個檔案」，這張回答「**名字 → 哪個宣告**」。
兩者同一個模式：由 resolve 建、以參數傳入、parse 不必知道它存在。

查表順序就是 Python 自己的名字解析規則，少一層都會連錯：

    ① 本檔宣告      class Bar: ...            → 同一個檔案裡的那個 Bar
    ② 本檔 import    from x import Bar         → x.py 裡的那個 Bar
    ③ 都不是         Exception、BaseModel      → builtins 或外部套件，查不到

**沒有第三步的全域搜尋。** 一個名字沒 import 進來就不在這個檔案的作用域裡，跨
檔案亂找同名的東西會連出一堆假邊——那正是 `resolve.md` §9.1 說的「外部不是判斷
出來的，是查不到的結果」。

這一版只到**檔案層級**：本檔的宣告全部算看得到，不分函式內外。作用域感知（誰
遮住誰）是 plan 5.5 的事，表的形狀不必為它改。規則見 docs/backend/resolve.md。
"""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

from app.parsers import Defines, Fact, Import
from app.resolve.edges import Resolver
from app.resolve.index import ModuleIndex


@dataclass(frozen=True)
class Declaration:
    """一個宣告住在哪個檔案、叫什麼、是哪一種。

    **刻意不存節點 id**：把名字接成 id 是 facts 層的事（`declarations.py` 就是
    這樣做的），這一層只回答名字的問題。
    """

    #: 宣告所在檔案的 `file:` 節點 id
    file: str
    #: 檔案內的完整路徑，如 ``Runner.run``
    qualified: str
    #: parse 用的字串種類："class" 或 "function"
    kind: str


@dataclass(frozen=True)
class Imported:
    """一個 import 進來的名字，來自哪個模組的什麼。

    `member` 是 `None` 代表綁到的是**模組本身**（`import x`）——那不是一個宣
    告，拿它當 base 查不到東西是對的。
    """

    #: 目標模組的節點 id（`file:` 或 `ext:`）
    module: str
    #: 從那個模組裡取出的原名。整包 ``import x`` 為 None
    member: str | None


@dataclass(frozen=True)
class NameIndex:
    """一次分析的名字知識。以參數傳入，不做成全域狀態（同 `ModuleIndex`）。"""

    #: 檔案 id → 完整路徑 → 宣告
    declared: Mapping[str, Mapping[str, Declaration]]
    #: 檔案 id → 本地名 → 來源
    imported: Mapping[str, Mapping[str, Imported]]

    def lookup(self, file_id: str, written: str) -> Declaration | None:
        """在 `file_id` 這個檔案裡，`written` 這個名字指向哪個宣告。

        `written` 是原始碼裡寫的樣子：`Bar`、`nx.Graph`、`Outer.Inner` 都吃得
        下。查不到回 `None`——那代表它是 builtin、外部套件，或這一版看不懂的寫
        法，三者在這裡不分，見 docs/backend/resolve.md §3.7。
        """
        # ① 本檔宣告。完整路徑直接比對，所以 `Outer.Inner` 這種也查得到。
        mine = self.declared.get(file_id, {})
        found = mine.get(written)
        if found is not None:
            return found

        # ② 本檔 import 進來的名字。
        here = self.imported.get(file_id, {})
        for head, attr in _splits(written):
            source = here.get(head)
            if source is None:
                continue
            # `nx.Graph` 要的是 Graph；`from x import Bar as B` 寫 B 要的是原名
            wanted = attr or source.member
            if wanted is None:
                # 綁到的是模組本身，不是宣告
                return None
            return self.declared.get(source.module, {}).get(wanted)
        return None


def from_facts(
    facts: Mapping[str, Sequence[Fact]],
    index: ModuleIndex,
    resolver: Resolver,
) -> NameIndex:
    """從 parse 的事實建表。`facts` 以來源檔案的節點 id 為 key。

    吃的是**整袋沒分型別的事實**，自己挑 `Defines` 與 `Import`：呼叫端
    （`pipeline.py`）因此不必提任何一種 Fact 的名字。

    import 的目標走 `resolver.target()`，跟 `imports` 邊用的是同一段程式碼——
    「`Bar` 從哪個檔案來」本來就是解一筆 import，相對 import、`__init__.py` 那
    些 per-language 規則不必在這裡重寫一次。
    """
    declared: dict[str, dict[str, Declaration]] = {}
    imported: dict[str, dict[str, Imported]] = {}

    for file_id in sorted(facts):
        mine: dict[str, Declaration] = {}
        here: dict[str, Imported] = {}

        # 事實依行號排序，所以後面的覆蓋前面的——跟 Python 自己一樣，重複的名字
        # 是後定義的那個贏。
        for fact in facts[file_id]:
            if isinstance(fact, Defines):
                qualified = _qualified(fact)
                mine[qualified] = Declaration(
                    file=file_id, qualified=qualified, kind=fact.kind
                )
            elif isinstance(fact, Import):
                bound = _bound_name(fact)
                found = resolver.target(fact, file_id, index)
                if bound is None or found is None:
                    continue
                here[bound] = Imported(module=found.target, member=fact.name)

        declared[file_id] = mine
        imported[file_id] = here

    return NameIndex(declared=declared, imported=imported)


def _splits(written: str) -> Iterator[tuple[str, str]]:
    """`a.b.Foo` → ("a.b.Foo", "")、("a.b", "Foo")、("a", "b.Foo")。

    最長的前綴先試：`import a.b` 綁的是 `a.b`，`import nx` 綁的是 `nx`，先長後
    短才兩種都對得上。
    """
    parts = written.split(".")
    for cut in range(len(parts), 0, -1):
        yield ".".join(parts[:cut]), ".".join(parts[cut:])


def _qualified(fact: Defines) -> str:
    return fact.name if fact.parent is None else f"{fact.parent}.{fact.name}"


def _bound_name(fact: Import) -> str | None:
    """這筆 import 在本檔綁出哪個名字。

    ``import a.b.c`` 綁的其實是 `a`，但後面接得上的寫法是 `a.b.c.Foo`，所以登記
    完整的點狀路徑，由 `_splits()` 去對——登記成 `a` 反而會把 `a.b.c` 錯當成 `a`
    底下的東西。
    """
    if fact.alias is not None:
        return fact.alias
    if fact.name is not None:
        return fact.name
    return fact.module or None
