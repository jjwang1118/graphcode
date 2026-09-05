"""Python 的名稱解析規則。

把 parser 給的字串接到圖上的節點。角色相當於 linker：`Import(module='app.graph')`
進來，`file:backend/app/graph/__init__.py` 出去。

**這是整條管線準確度的瓶頸**——前面解析得再對，這裡接錯檔案，圖就是錯的，而
且畫面上看不出來。規則見 docs/backend/resolve.md。
"""

from app.models import NodeType, make_id
from app.parsers import Import
from app.resolve.index import ModuleIndex, Resolution


class PythonResolver:
    def target(
        self, fact: Import, importer_id: str, index: ModuleIndex
    ) -> Resolution | None:
        """這筆 import 指向哪個節點；相對 import 對不到時回 `None`。"""
        if fact.level > 0:
            return _relative(fact, importer_id, index)
        return _absolute(fact, importer_id, index)


def _absolute(fact: Import, importer_id: str, index: ModuleIndex) -> Resolution:
    """絕對 import。查不到不是失敗，是「這個名字不在專案裡」＝外部套件。"""
    for module in _candidates(fact.module, fact.name, separator="."):
        found = index.lookup(module, importer_id)
        if found is not None:
            return found

    # 外部套件取最頂層：import fastapi 與 from fastapi.routing import X 是同一個
    # 套件，該是同一個節點。完整路徑留在邊的 properties 裡，資訊沒丟。
    top = (fact.module or "").split(".")[0]
    return Resolution(target=make_id(NodeType.EXTERNAL_PACKAGE, top))


def _relative(fact: Import, importer_id: str, index: ModuleIndex) -> Resolution | None:
    """相對 import。照定義就是路徑相對，所以走路徑不走模組名。

    `level` 是往上幾層：1 = 自己的目錄，2 = 再上一層。爬出專案外時回 `None`
    ——Python 自己也不允許（attempted relative import beyond top-level package），
    那是原始碼的問題，不該硬造一個外部套件節點來充數。
    """
    directory = _directory(_path(importer_id))
    for _ in range(fact.level - 1):
        if not directory:
            return None
        directory = _directory(directory)

    base = directory
    if fact.module:
        base = _join(base, fact.module.replace(".", "/"))

    for path in _candidates(base, fact.name, separator="/"):
        found = index.at_path(path)
        if found is not None:
            return Resolution(target=found)
    return None


def _candidates(base: str | None, name: str | None, separator: str) -> list[str]:
    """先窄後寬：`name` 可能是子模組，先當子模組試，沒有才退回 `base` 本身。

    順序反過來的話，`from app.graph.query import CodeGraph` 也會退化成指向
    package 的 `__init__.py`，圖的解析度就沒了。
    """
    if base is None:
        return []
    if name is None:
        return [base]
    return [f"{base}{separator}{name}" if base else name, base]


def _join(directory: str, tail: str) -> str:
    return f"{directory}/{tail}" if directory else tail


def _directory(path: str) -> str:
    head, separator, _ = path.rpartition("/")
    return head if separator else ""


def _path(node_id: str) -> str:
    return node_id.partition(":")[2]
