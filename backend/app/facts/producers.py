"""型別 → 產生器的表，以及套用它的那個迴圈。

**加一種 Fact ＝ 這張表加一筆 ＋ 寫一個產生器**，`pipeline.py` 與 `build.py`
都不必動——plan 5.2 的完成條件就是這句話。這個分流曾經是 `pipeline.py` 裡誠實
寫死的兩段，`Inherits` 與 `Calls` 一來就會變成四段。

表的 key 是 Fact 的**型別本身**而不是字串：打錯名字在 import 的當下就炸掉，而
不是安靜地少一批節點。規格見 docs/backend/facts.md。
"""

from collections import Counter
from collections.abc import Mapping, Sequence

from app.facts.declarations import DeclarationProducer
from app.facts.imports import ImportProducer
from app.facts.inherits import InheritsProducer
from app.facts.production import Context, Producer, Production
from app.models import Edge, Node
from app.parsers import Defines, Fact, Import, Inherits


class UnknownFactError(Exception):
    """有一種 Fact 沒有人接。"""


#: 型別 → 誰負責把它接上圖。之後：`Calls`（5.6）
#:
#: 順序就是產生器被呼叫的順序，也就是輸出裡節點與邊的順序（F4）。新的掛在最
#: 後，既有的相對順序不動。
PRODUCERS: dict[type, Producer] = {
    Defines: DeclarationProducer(),
    Import: ImportProducer(),
    Inherits: InheritsProducer(),
}


def to_graph(
    facts: Mapping[str, Sequence[Fact]],
    context: Context,
    producers: Mapping[type, Producer] = PRODUCERS,
) -> Production:
    """分堆 → 查表 → 合併。`facts` 以來源檔案的節點 id 為 key。

    `producers` 收成參數是為了測試餵得進一張假表——正式路徑一律用預設的那張。
    """
    grouped = _by_type(facts)

    unknown = sorted(kind.__name__ for kind in grouped if kind not in producers)
    if unknown:
        # 副檔名查不到 parser 是正常的（那個檔案就是不 parse），這裡不是：parser
        # 吐出一種沒人接的事實，代表表漏了一筆，安靜跳過就是圖裡少東西。
        raise UnknownFactError(f"沒有產生器認得這種事實：{', '.join(unknown)}")

    nodes: list[Node] = []
    edges: list[Edge] = []
    counters: Counter[str] = Counter()

    # 依**表**的順序跑，不是依事實出現的順序——輸出的節點順序才不會隨著原始碼
    # 裡先寫 import 還是先寫 class 而變動。
    for kind, producer in producers.items():
        mine = grouped.get(kind)
        if mine is None:
            continue
        produced = producer.produce(mine, context)
        nodes.extend(produced.nodes)
        edges.extend(produced.edges)
        counters.update(produced.counters)

    return Production(nodes=tuple(nodes), edges=tuple(edges), counters=dict(counters))


def _by_type(
    facts: Mapping[str, Sequence[Fact]],
) -> dict[type, dict[str, list[Fact]]]:
    """「檔案 → 各種事實」翻成「型別 → 檔案 → 這一種事實」。

    每個產生器只看得到自己那一堆，所以它裡面不必再寫一次 `isinstance`。
    """
    grouped: dict[type, dict[str, list[Fact]]] = {}
    for file_id in sorted(facts):
        for fact in facts[file_id]:
            grouped.setdefault(type(fact), {}).setdefault(file_id, []).append(fact)
    return grouped
