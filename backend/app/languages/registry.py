"""語言 registry：副檔名 → 這個語言的 parser 與 resolver。

**一筆同時掛兩者**，不是兩張表。分開的話有可能只加一半——parser 有、resolver
漏掉，結果是解析得出事實卻接不到節點，而且不會報錯。

裝的是**語言知識**（這個語言的 import 怎麼寫、名字怎麼變成檔案），對每個專案
都一樣；**專案知識**（有哪些檔案）只有 resolve 拿得到，走參數傳入。兩者都不做
成可變的全域狀態。

新增語言 = 這張表加一筆，parse 與 resolve 的程式碼都不動。
"""

from dataclasses import dataclass

from app.parsers import Parser, PythonParser
from app.resolve import PythonResolver, Resolver


@dataclass(frozen=True)
class Language:
    parser: Parser
    resolver: Resolver


LANGUAGES: dict[str, Language] = {
    ".py": Language(parser=PythonParser(), resolver=PythonResolver()),
}


def for_path(path: str) -> Language | None:
    """這個檔案該用哪個語言處理；查不到就是不 parse（正常，不是錯誤）。"""
    _, separator, suffix = path.rpartition(".")
    return LANGUAGES.get(f".{suffix}") if separator else None
