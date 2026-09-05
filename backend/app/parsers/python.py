"""Python 的 parser，用標準庫的 `ast`。

選 `ast` 的理由與代價見 docs/backend/parse.md。代價是**解析失敗即整份檔案歸
零**——語法錯誤，或原始碼用了比後端這個 Python 版本更新的語法，都會讓這個檔
案一個 import 都拿不到。所以失敗一律顯性回報，不靜靜跳過。
"""

import ast
from collections.abc import Iterator

from app.parsers.facts import Import, ParseResult


class PythonParser:
    def parse(self, source: str) -> ParseResult:
        try:
            tree = ast.parse(source)
        except SyntaxError as error:
            return ParseResult(error=_describe(error))
        except ValueError as error:
            # 副檔名是 .py 但內容是二進位（含空位元組）時 ast 拋這個。同樣是
            # 「這個檔案有問題」，不是我們的 bug，所以照失敗處理。
            return ParseResult(error=str(error))

        # 依行號排序，讓輸出跟著原始碼的順序走（ast.walk 是廣度優先）。排序
        # 穩定，所以同一行內的多個名字維持原順序。
        return ParseResult(
            facts=tuple(sorted(_imports(tree), key=lambda fact: fact.line))
        )


def _describe(error: SyntaxError) -> str:
    if error.lineno is None:
        return error.msg
    return f"{error.msg} (line {error.lineno})"


def _imports(tree: ast.AST) -> Iterator[Import]:
    # 走整棵樹而不是只看頂層：`if TYPE_CHECKING:` 內與函式內的 import 都算。
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # import a.b.c as abc —— 整包拿進來，沒有「從裡面取出什麼」
            for alias in node.names:
                yield Import(
                    module=alias.name,
                    level=0,
                    name=None,
                    alias=alias.asname,
                    line=node.lineno,
                )
        elif isinstance(node, ast.ImportFrom):
            # from foo import bar —— node.module 是 None 代表 `from . import x`
            for alias in node.names:
                yield Import(
                    module=node.module,
                    level=node.level,
                    name=alias.name,
                    alias=alias.asname,
                    line=node.lineno,
                )
