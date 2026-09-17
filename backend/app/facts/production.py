"""產生器的契約：一種 Fact 進來，節點、邊與計數出去。

Fact 有兩種命運——**宣告**只看一個檔案就答得出來，直接變節點；**引用**要比對
全域索引才知道指向誰，得繞一趟 resolve。差別關在各自的產生器裡，對查表的那一
層是同一個形狀。

`Context` 裝的是產生器可能要用到的**專案知識**（有哪些檔案）與**語言知識**
（這個語言的名字怎麼解析）。兩者都以參數傳入、不做成可變的全域狀態，理由與
`app/languages/` 那張 registry 相同。規格見 docs/backend/facts.md。
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.languages import Language
from app.models import Edge, Node
from app.resolve import ModuleIndex, NameIndex


@dataclass(frozen=True)
class Context:
    """產生器手上能有的全部背景知識。

    不給 `facts` 以外的東西：產生器看得到誰，決定了它可能依賴誰。

    兩張表都是唯讀的查詢介面，**不是別的產生器的輸出**：`names` 雖然是宣告事實
    的產物，但它由 resolve 從同一份事實建好再傳進來，產生器之間仍然互不相識
    （`facts.md` §9 預告的走法）。
    """

    index: ModuleIndex
    language: Language
    #: 名字 → 宣告。`Inherits` 要靠它把 `class Foo(Bar)` 的 `Bar` 接到節點
    names: NameIndex


@dataclass(frozen=True)
class Production:
    """一個產生器交出來的東西。

    節點與邊都可能有：`Import` 對不到專案內的檔案時要順手造出
    `external_package` 節點，只回邊的話那條邊會指向不存在的節點，被 build 的
    B2 擋下來。
    """

    nodes: tuple[Node, ...] = ()
    edges: tuple[Edge, ...] = ()
    #: 要記進 `meta` 的計數。**key 就是 `Diagnostics` 的欄位名**——這一層不認識
    #: `Diagnostics`，但約好用同一組名字，pipeline 就不必提任何計數的名字。
    counters: Mapping[str, int] = field(default_factory=dict)


class Producer(Protocol):
    """吃一種 Fact，不吃全部。

    `facts` 以**來源檔案的節點 id** 為 key（fact 自己不知道它從哪個檔案來），
    而且**只含這個產生器負責的那一種型別**——分堆是 `producers.to_graph` 的
    事，產生器裡面不必再濾一次。

    這裡的元素型別寫成 `Any`：表是異質的，各個產生器在自己的簽章上寫清楚它吃
    的是 `Defines` 還是 `Import`。
    """

    def produce(
        self, facts: Mapping[str, Sequence[Any]], context: Context
    ) -> Production: ...
