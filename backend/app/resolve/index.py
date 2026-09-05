"""全域檔案索引：模組名 → 節點 id。

resolve 的難處是**同一個檔案叫什麼名字，取決於從哪裡開始數**：

    external / CFRU / utils / fflow.py
    └────────────────────────────────┘  external.CFRU.utils.fflow
               └─────────────────────┘  CFRU.utils.fflow
                       └─────────────┘  utils.fflow     ← import utils.fflow 要的是這個
                               └─────┘  fflow

起點在哪沒有寫在 import 語句裡。**所以不猜，每一種數法都登記**——誰對得上算
誰。曾經考慮用 `__init__.py` 判斷起點，但 Python 3.3 之後不需要它也能 import，
實測研究型專案幾乎都不寫，那樣做會把專案內部的檔案誤判成外部套件。

代價是短名字（`utils`、`main`）容易撞號，由 `lookup()` 取最近的並標記。規則見
docs/backend/resolve.md。
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.models import NodeType, make_id

_INIT = "__init__.py"
_SUFFIX = ".py"


@dataclass(frozen=True)
class Resolution:
    """查表的結果。

    `ambiguous` 只在撞號時有值，裝的是**全部**候選（含選中的那個）。只記一個
    布林值的話，知道有問題也查不下去。
    """

    target: str
    ambiguous: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModuleIndex:
    """一次分析的專案知識。以參數傳入，不做成全域狀態。

    絕對 import 查 `by_module`，相對 import 走 `at_path()`——相對 import 照定義
    就是路徑相對，不必經過模組名。
    """

    #: 模組名 → 節點 id（排序過；多於一個代表撞號）
    by_module: Mapping[str, tuple[str, ...]]
    #: 專案裡所有 .py 的相對路徑
    files: frozenset[str]

    def lookup(self, module: str, importer_id: str) -> Resolution | None:
        """絕對 import：查模組名。"""
        candidates = self.by_module.get(module)
        if not candidates:
            return None
        if len(candidates) == 1:
            return Resolution(target=candidates[0])
        return Resolution(
            target=_nearest(candidates, importer_id), ambiguous=candidates
        )

    def at_path(self, path: str) -> str | None:
        """相對 import：這個路徑上有沒有模組（`x.py` 或 `x/__init__.py`）。"""
        if not path:
            return None
        for candidate in (f"{path}{_SUFFIX}", f"{path}/{_INIT}"):
            if candidate in self.files:
                return make_id(NodeType.FILE, candidate)
        return None


def from_files(files: Sequence[str]) -> ModuleIndex:
    """從 scan 的檔案清單建索引。`files` 是相對於 repo 根的路徑。"""
    by_module: dict[str, list[str]] = {}
    sources = frozenset(path for path in files if path.endswith(_SUFFIX))

    for path in sorted(sources):
        node_id = make_id(NodeType.FILE, path)
        for module in _module_names(path):
            by_module.setdefault(module, []).append(node_id)

    return ModuleIndex(
        by_module={module: tuple(ids) for module, ids in by_module.items()},
        files=sources,
    )


def _module_names(path: str) -> list[str]:
    """這個檔案所有可能的模組名，長的在前。"""
    parts = path.split("/")
    # __init__.py 代表的是它所在的目錄，自己不佔一段。
    segments = (
        parts[:-1] if parts[-1] == _INIT else [*parts[:-1], parts[-1][: -len(_SUFFIX)]]
    )

    return [".".join(segments[start:]) for start in range(len(segments))]


def _nearest(candidates: tuple[str, ...], importer_id: str) -> str:
    """撞號時取路徑上最近的那個。

    `max` 回傳第一個最大值，而 `candidates` 是排序過的，所以平手時取排序第一
    ——不是因為那樣猜得準，是為了**可重現**：同一個專案分析兩次要得到同一張圖。
    """
    return max(candidates, key=lambda node_id: _shared(node_id, importer_id))


def _shared(left_id: str, right_id: str) -> int:
    """兩個檔案共用幾層目錄。比的是「段」不是字元，否則 `back` 會像 `backend`。"""
    left = _path(left_id).split("/")[:-1]
    right = _path(right_id).split("/")[:-1]

    shared = 0
    for one, other in zip(left, right):
        if one != other:
            break
        shared += 1
    return shared


def _path(node_id: str) -> str:
    return node_id.partition(":")[2]
