"""一次分析：根目錄 → 圖。

把 scan / parse / resolve / build 串起來的地方。**不放在 `app/api/`**——API 層
只該做 HTTP（解析請求、轉錯誤碼），不該知道管線有幾段；分開之後管線也能不啟動
FastAPI 就測。

管線是單向的：每一段只吃前一段的輸出。這裡唯一的例外是 scan 的節點會等到
parse 跑完才交給 build，因為解析失敗的訊息要貼回對應的 `file` 節點。
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from app.graph import CodeGraph, build
from app.graph.build import Diagnostics
from app.languages import Language, for_path
from app.models import Edge, Node, NodeType, make_id
from app.parsers import Fact
from app.resolve import from_files, to_edges
from app.scan import from_root


def analyze(root: Path) -> CodeGraph:
    """走完整條管線。`root` 必須已經通過 ingest 的檢查。"""
    scanned = from_root(root)
    parsed = _parse_all(root, scanned.files)
    index = from_files(scanned.files)

    nodes: list[Node] = [_annotated(node, parsed.errors) for node in scanned.nodes]
    edges: list[Edge] = list(scanned.edges)
    ambiguous = 0
    unresolved = 0

    # 依語言分組：名稱解析規則是 per-language，不能拿 Python 的規則去解 TS 的
    # import。目前只有一組，但寫成迴圈，加語言時這裡不用改。
    for language, facts in parsed.facts.items():
        resolved = to_edges(facts, index, language.resolver)
        nodes.extend(resolved.nodes)
        edges.extend(resolved.edges)
        ambiguous += resolved.ambiguous
        unresolved += resolved.unresolved

    return build(
        nodes,
        edges,
        diagnostics=Diagnostics(
            parse_failures=len(parsed.errors),
            ambiguous_imports=ambiguous,
            unresolved_imports=unresolved,
        ),
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
