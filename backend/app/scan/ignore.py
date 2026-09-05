"""走訪時要跳過的名字。

雜訊過濾，與安全無關（安全的閘門在 ingest）。之後若改成讀專案自己的
`.gitignore`，只換這個模組，`walk.py` 不動。規則見 docs/backend/scan.md。
"""

from collections.abc import Collection

#: 預設忽略的名字。比對的是名字本身，不是路徑，也不做樣式比對。
DEFAULT_IGNORE: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        "dist",
        "build",
        ".venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
)


def is_ignored(name: str, ignore: Collection[str] = DEFAULT_IGNORE) -> bool:
    return name in ignore
