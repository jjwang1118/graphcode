"""節點 id 的組法與拆法。

`PREFIX` 是前綴的唯一出處；其他模組一律呼叫 `make_id()` / `owner_file()`，
不自己拼字串。規則見 docs/backend/graph_schema.md › id 規則。
"""

from app.models.types import NodeType

#: 型別 → id 前綴。前綴不等於型別名，所以需要這張表。
PREFIX: dict[NodeType, str] = {
    NodeType.REPO: "repo",
    NodeType.DIRECTORY: "dir",
    NodeType.FILE: "file",
    NodeType.EXTERNAL_PACKAGE: "ext",
    NodeType.MODULE: "module",
    NodeType.CLASS: "class",
    NodeType.FUNCTION: "function",
}

#: repo 節點的路徑基底：根目錄自己的相對路徑。
ROOT_PATH = "."

#: 檔案內的實體與所屬檔案之間的分隔符。
MEMBER_SEP = "::"

# 路徑基底是一個檔案的型別，只有這些推得出所屬檔案。
_FILE_SCOPED = frozenset({NodeType.FILE, NodeType.CLASS, NodeType.FUNCTION})

_TYPE_BY_PREFIX = {prefix: node_type for node_type, prefix in PREFIX.items()}


def make_id(node_type: NodeType, path: str, member: str | None = None) -> str:
    """組出節點 id。

    `path` 必須相對於 repo 根；`member` 是檔案內實體的名字（如 `Runner.run`）。
    """
    node_id = f"{PREFIX[node_type]}:{_normalize_path(path)}"
    if member is None:
        return node_id
    return f"{node_id}{MEMBER_SEP}{member}"


def owner_file(node_id: str) -> str | None:
    """回傳這個 id 所屬的 `file` 節點 id；不屬於任何檔案時回 `None`。

    無法辨識的 id 也回 `None`。
    """
    prefix, _, rest = node_id.partition(":")
    if _TYPE_BY_PREFIX.get(prefix) not in _FILE_SCOPED:
        return None
    path = rest.split(MEMBER_SEP, 1)[0]
    return f"{PREFIX[NodeType.FILE]}:{path}"


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/").rstrip("/")
    if not normalized:
        raise ValueError("path 不可為空")
    if normalized.startswith("/") or ":" in normalized.split("/")[0]:
        raise ValueError(f"path 必須相對於 repo 根：{path!r}")
    return normalized
