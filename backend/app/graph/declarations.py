"""宣告事實 → `class` / `function` 節點 ＋ `defines` 邊。

`Import` 要比對全域索引才知道指向誰，宣告不必——**它自己就是節點**。所以這裡
不查任何索引，是一個純粹的對應層，餵一份假的 fact 就測得動。

放在 `app/graph/` 而不是 parse 或 resolve：產出就是 build 的輸入，而 CLAUDE.md
把「`Fact → 節點/邊` 的對應規則」這條例外掛在 build 名下。**這是暫時的家**，
plan 5.2 要做的就是讓它變成不認識具體型別的通用迴圈。規則見
docs/backend/graph.md。
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.models import Edge, EdgeType, Node, NodeType, make_id
from app.models.ids import PREFIX
from app.parsers import Defines, Fact

#: parse 用字串講種類（它不認識 app.models），在這裡換回型別。
_NODE_TYPE = {"class": NodeType.CLASS, "function": NodeType.FUNCTION}


@dataclass(frozen=True)
class DeclareResult:
    """`defines` 那一半的圖。

    沒有「解析失敗」的計數：宣告不需要解析，抽得到就是對的。檔案整份解析失敗
    的情況由 `meta.parse_failures` 涵蓋。
    """

    nodes: tuple[Node, ...] = ()
    edges: tuple[Edge, ...] = ()


def to_nodes(facts: Mapping[str, Sequence[Fact]]) -> DeclareResult:
    """`facts` 以來源檔案的節點 id 為 key——fact 自己不知道它從哪個檔案來。"""
    nodes: list[Node] = []
    edges: list[Edge] = []

    for file_id in sorted(facts):
        path = _path_of(file_id)
        declared = [fact for fact in facts[file_id] if isinstance(fact, Defines)]
        # 完整路徑 → 種類。父節點的 id 要知道父是 class 還是 function，而 parse
        # 保證父一定先出現。同名的 class 與 def 撞在一起時後者勝，跟 Python 自
        # 己的語意一致（後定義的蓋掉前面的）。
        kinds = {_qualified(fact): fact.kind for fact in declared}

        groups: dict[str, list[Defines]] = {}
        for fact in declared:
            groups.setdefault(_id_of(path, fact), []).append(fact)

        for node_id, group in groups.items():
            kept = _implementation(group)
            shadowed = sorted(one.line for one in group if one is not kept)
            nodes.append(
                Node(
                    id=node_id,
                    type=_NODE_TYPE[kept.kind],
                    label=kept.name,
                    properties=_properties(kept, shadowed),
                )
            )
            edges.append(
                Edge(
                    source=_parent_id(path, kept, kinds),
                    target=node_id,
                    type=EdgeType.DEFINES,
                )
            )

    return DeclareResult(nodes=tuple(nodes), edges=tuple(edges))


def _implementation(group: Sequence[Defines]) -> Defines:
    """同一個作用域內同名的宣告只能有一個節點，這裡決定留哪一筆。

    Python 允許同名：`@overload`、`@property` 配 `.setter`、`if` 兩個分支各定
    義一次。而 `build()` 對重複的 id 直接丟 `BuildError`——**不去重就是整次分
    析零結果**，實測 pydantic 4.5%、anyio 7.4% 的宣告會撞。

    挑「第一筆不是 `@overload` 的」：實測 58 個 overload 群組的**實作全部在最
    後一筆**，挑第一筆會讓行號指到空殼；而 14 個 property 群組的第一筆就是
    getter。固定挑第一筆或最後一筆都會錯掉其中一半。
    """
    for one in group:
        if not one.overload:
            return one
    # 整組都是簽章（.pyi 風格），沒有實作可挑。留第一筆，至少讓節點存在——
    # 讓它整個消失比行號指到空殼更糟。
    return group[0]


def _properties(kept: Defines, shadowed: Sequence[int]) -> dict[str, Any]:
    """被合併掉的那幾筆不丟掉，記行號。

    跟 `ambiguous`、`internal_imports` 同一套處置：資訊留在 `properties` 裡，
    問得出來「這個節點其實有幾個同名的宣告」。
    """
    if not shadowed:
        return {"line": kept.line}
    return {"line": kept.line, "redefined_at": list(shadowed)}


def _id_of(path: str, fact: Defines) -> str:
    return make_id(_NODE_TYPE[fact.kind], path, member=_qualified(fact))


def _parent_id(path: str, fact: Defines, kinds: Mapping[str, str]) -> str:
    """頂層宣告掛在檔案上，其餘掛在包住它的那個宣告上。"""
    if fact.parent is None:
        return make_id(NodeType.FILE, path)
    return make_id(_NODE_TYPE[kinds[fact.parent]], path, member=fact.parent)


def _qualified(fact: Defines) -> str:
    """節點 id 裡 `::` 後面那一段，如 `Runner.run`。"""
    return fact.name if fact.parent is None else f"{fact.parent}.{fact.name}"


def _path_of(file_id: str) -> str:
    """`file:app/graph/build.py` → `app/graph/build.py`。

    facts 是以 `file` 節點 id 為 key 交進來的，而 `make_id()` 要的是路徑。
    """
    prefix, _, path = file_id.partition(":")
    if prefix != PREFIX[NodeType.FILE]:
        raise ValueError(f"不是 file 節點的 id：{file_id!r}")
    return path
