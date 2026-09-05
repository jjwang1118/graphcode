"""節點與邊的型別詞彙。

封閉清單，來源是 CLAUDE.md › 圖模型的兩張表。
"""

from enum import StrEnum


class NodeType(StrEnum):
    # 第一階段實際產出
    REPO = "repo"
    DIRECTORY = "directory"
    FILE = "file"
    EXTERNAL_PACKAGE = "external_package"
    # schema 已定義、尚未填充
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"


class EdgeType(StrEnum):
    # 第一階段實際產出
    CONTAINS = "contains"
    IMPORTS = "imports"
    # schema 已定義、尚未填充
    DEFINES = "defines"
    CALLS = "calls"
    INHERITS = "inherits"
