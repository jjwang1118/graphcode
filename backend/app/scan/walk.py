"""走訪根目錄，產出 `file` / `directory` 節點與 `contains` 邊。

規則見 docs/backend/scan.md。
"""

from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path

from app.models import Edge, EdgeType, Node, NodeType, make_id
from app.models.ids import ROOT_PATH
from app.scan.ignore import DEFAULT_IGNORE, is_ignored


@dataclass
class ScanResult:
    """圖的 `contains` 那一半，以及要送去 parse 的檔案清單。"""

    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


def from_root(root: Path, ignore: Collection[str] = DEFAULT_IGNORE) -> ScanResult:
    """走訪 `root`，回傳節點、`contains` 邊與檔案清單。"""
    repo_id = make_id(NodeType.REPO, ROOT_PATH)
    result = ScanResult(nodes=[Node(id=repo_id, type=NodeType.REPO, label=root.name)])
    _walk(root, root, repo_id, ignore, result)
    return result


def _walk(
    directory: Path,
    root: Path,
    parent_id: str,
    ignore: Collection[str],
    result: ScanResult,
) -> None:
    for entry in sorted(directory.iterdir(), key=lambda path: path.name):
        # symlink 會逃出 allowlist，也可能指回祖先造成無限遞迴。
        if is_ignored(entry.name, ignore) or entry.is_symlink():
            continue

        relative = entry.relative_to(root).as_posix()
        if entry.is_dir():
            node_id = make_id(NodeType.DIRECTORY, relative)
            result.nodes.append(
                Node(id=node_id, type=NodeType.DIRECTORY, label=entry.name)
            )
            result.edges.append(_contains(parent_id, node_id))
            _walk(entry, root, node_id, ignore, result)
        elif entry.is_file():
            node_id = make_id(NodeType.FILE, relative)
            result.nodes.append(Node(id=node_id, type=NodeType.FILE, label=entry.name))
            result.edges.append(_contains(parent_id, node_id))
            result.files.append(relative)


def _contains(parent_id: str, child_id: str) -> Edge:
    return Edge(source=parent_id, target=child_id, type=EdgeType.CONTAINS)
