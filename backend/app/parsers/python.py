"""Python 的 parser，用標準庫的 `ast`。

選 `ast` 的理由與代價見 docs/backend/parse.md。代價是**解析失敗即整份檔案歸
零**——語法錯誤，或原始碼用了比後端這個 Python 版本更新的語法，都會讓這個檔
案一個 import 都拿不到。所以失敗一律顯性回報，不靜靜跳過。
"""

import ast
from collections.abc import Iterator
from typing import Literal

from app.parsers.facts import Defines, Fact, Import, ParseResult


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

        # 依行號排序，讓輸出跟著原始碼的順序走（走訪順序與原始碼無關）。排序
        # 穩定，所以同一行內的多個名字維持原順序。
        return ParseResult(
            facts=tuple(sorted(_facts(tree, None), key=lambda fact: fact.line))
        )


def _describe(error: SyntaxError) -> str:
    if error.lineno is None:
        return error.msg
    return f"{error.msg} (line {error.lineno})"


def _facts(node: ast.AST, scope: str | None) -> Iterator[Fact]:
    """走整棵樹，同時記住現在在哪個宣告裡面。

    不用 `ast.walk` 是因為它是廣度優先，拿不到「誰包住誰」。走整棵樹這件事不
    變：`if TYPE_CHECKING:` 內與函式內的 import 與宣告都算。
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Import | ast.ImportFrom):
            yield from _imports(child)
            continue

        declared = _declaration(child, scope)
        if declared is None:
            # 不是宣告——繼續往下找，作用域不變。`if TYPE_CHECKING:` 或 `try:`
            # 裡面的宣告仍然屬於外面那一層，不會多包一層。
            yield from _facts(child, scope)
            continue

        yield declared
        yield from _facts(child, _qualified(scope, declared.name))


def _imports(node: ast.Import | ast.ImportFrom) -> Iterator[Import]:
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
        return

    # from foo import bar —— node.module 是 None 代表 `from . import x`
    for alias in node.names:
        yield Import(
            module=node.module,
            level=node.level,
            name=alias.name,
            alias=alias.asname,
            line=node.lineno,
        )


def _declaration(node: ast.AST, scope: str | None) -> Defines | None:
    if isinstance(node, ast.ClassDef):
        kind: Literal["class", "function"] = "class"
    elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        kind = "function"
    else:
        return None

    # lineno 是 `def` / `class` 那一行；裝飾器有自己的 lineno，ast 已經分開，
    # 不必自己往回扣。跳過去看到的是宣告本身，不是一個裝飾器。
    return Defines(
        kind=kind,
        name=node.name,
        parent=scope,
        line=node.lineno,
        overload=_is_overload(node),
    )


def _is_overload(node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """`@overload` 與 `@typing.overload` 都算。

    只看字面的最後一段：parser 沒有全域視野，不知道那個名字實際指向誰。誤判的
    代價是同名的兩筆挑錯一筆，不會產生錯的邊。
    """
    return any(
        ast.unparse(decorator).split("(")[0].rsplit(".", 1)[-1] == "overload"
        for decorator in node.decorator_list
    )


def _qualified(scope: str | None, name: str) -> str:
    return name if scope is None else f"{scope}.{name}"
