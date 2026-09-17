"""一次分析：根目錄 → 圖。

把 scan / parse / resolve / build 串起來的地方。**不放在 `app/api/`**——API 層
只該做 HTTP（解析請求、轉錯誤碼），不該知道管線有幾段；分開之後管線也能不啟動
FastAPI 就測。

管線是單向的：每一段只吃前一段的輸出。這裡唯一的例外是 scan 的節點會等到
parse 跑完才交給 build，因為解析失敗的訊息要貼回對應的 `file` 節點。
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from app.facts import Context, to_graph
from app.graph import CodeGraph, build
from app.graph.build import Diagnostics
from app.languages import Language, for_path
from app.models import Edge, Node, NodeType, make_id
from app.parsers import Fact
from app.resolve import from_facts, from_files
from app.scan import from_root


def analyze(root: Path) -> CodeGraph:
    """走完整條管線。`root` 必須已經通過 ingest 的檢查。"""
    scanned = from_root(root)
    parsed = _parse_all(root, scanned.files)
    index = from_files(scanned.files)

    nodes: list[Node] = [_annotated(node, parsed.errors) for node in scanned.nodes]
    edges: list[Edge] = list(scanned.edges)
    counts: Counter[str] = Counter()

    # 依語言分組：名稱解析規則是 per-language，不能拿 Python 的規則去解 TS 的
    # import。目前只有一組，但寫成迴圈，加語言時這裡不用改。
    for language, facts in parsed.facts.items():
        # 兩張表都在這裡建好才進 Context：一張是「模組名 → 檔案」（吃 scan 的檔
        # 案清單），一張是「名字 → 宣告」（吃這個語言的全部事實，自己挑它要的
        # 型別）。產生器只查表，不自己建表，彼此也就不必互相認識。
        names = from_facts(facts, index, language.resolver)
        # 哪一種事實走哪條路寫在 app/facts/ 的表裡，這裡只負責把它跑一遍——
        # **加一種 Fact 不必動這個檔案**。
        produced = to_graph(facts, Context(index=index, language=language, names=names))
        nodes.extend(produced.nodes)
        edges.extend(produced.edges)
        counts.update(produced.counters)

    return build(
        nodes,
        edges,
        # `counts` 的 key 就是 `Diagnostics` 的欄位名，所以這裡不必提任何一個
        # 計數的名字；`parse_failures` 不是任何 Fact 的產物（整份檔案都沒解析
        # 出來，一筆事實都沒有），仍由這裡算。
        diagnostics=Diagnostics(parse_failures=len(parsed.errors), **counts),
    )


@dataclass
class _Parsed:
    #: 語言 → { 來源檔案節點 id → 事實 }
    facts: dict[Language, dict[str, list[Fact]]] = field(default_factory=dict)
    #: 檔案節點 id → 解析失敗的原因
    errors: dict[str, str] = field(default_factory=dict)


def _parse_all(root: Path, files: Iterable[str]) -> _Parsed:
    parsed = _Parsed()
    for relative in files:
        language = for_path(relative)
        if language is None:
            # 副檔名不認得就不 parse。「進圖但不 parse」是正常的，不是失敗。
            continue

        node_id = make_id(NodeType.FILE, relative)
        result = language.parser.parse(_read(root / relative))
        if result.error is not None:
            parsed.errors[node_id] = result.error
            continue
        if result.facts:
            parsed.facts.setdefault(language, {})[node_id] = list(result.facts)
    return parsed


def _annotated(node: Node, errors: dict[str, str]) -> Node:
    """把解析失敗的原因貼回 `file` 節點。

    節點是 scan 產的、錯誤是 parse 產的，兩者在這裡會合。不做成 build 的工作，
    因為 build 的定位是「不在乎節點從哪來」。
    """
    error = errors.get(node.id)
    if error is None:
        return node
    return node.model_copy(
        update={"properties": {**node.properties, "parse_error": error}}
    )


def _read(path: Path) -> str:
    # 讀不出 UTF-8 的位元組原樣留著：那是檔案本身的問題，交給 parser 回報，
    # 不該在這裡讓整次分析中斷。
    return path.read_text(encoding="utf-8", errors="surrogateescape")
