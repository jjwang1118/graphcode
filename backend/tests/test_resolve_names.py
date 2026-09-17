"""名字表（N1–N7）。

查表順序就是 Python 自己的規則：本檔宣告 → 本檔 import → 查不到。**沒有全域搜
尋**，所以「另一個檔案裡有同名的 class」不該被查到——那一條是這裡最重要的斷言。
"""

from collections.abc import Mapping, Sequence

from app.parsers import Defines, Fact, Import
from app.resolve import NameIndex, PythonResolver, from_facts, from_files

APP = "file:src/app.py"
LIB = "file:src/lib.py"


def index(facts: Mapping[str, Sequence[Fact]]) -> NameIndex:
    files = ["src/app.py", "src/lib.py", "src/pkg/__init__.py", "src/pkg/thing.py"]
    return from_facts(facts, from_files(files), PythonResolver())


def lookup(
    facts: Mapping[str, Sequence[Fact]], written: str, where: str = APP
) -> str | None:
    found = index(facts).lookup(where, written)
    return None if found is None else f"{found.file}::{found.qualified}#{found.kind}"


def test_a_name_declared_in_this_file_wins() -> None:
    facts: dict[str, list[Fact]] = {
        APP: [Defines(kind="class", name="Bar", parent=None, line=1)]
    }

    assert lookup(facts, "Bar") == f"{APP}::Bar#class"


def test_a_name_imported_from_another_file_lands_on_that_declaration() -> None:
    facts: dict[str, list[Fact]] = {
        APP: [Import(module="src.lib", level=0, name="Bar", alias=None, line=1)],
        LIB: [Defines(kind="class", name="Bar", parent=None, line=1)],
    }

    assert lookup(facts, "Bar") == f"{LIB}::Bar#class"


def test_an_alias_is_looked_up_by_its_original_name() -> None:
    facts: dict[str, list[Fact]] = {
        APP: [Import(module="src.lib", level=0, name="Bar", alias="B", line=1)],
        LIB: [Defines(kind="class", name="Bar", parent=None, line=1)],
    }

    assert lookup(facts, "B") == f"{LIB}::Bar#class"
    # 別名在本檔叫 B，原名 Bar 在這個檔案裡是看不到的
    assert lookup(facts, "Bar") is None


def test_a_dotted_name_takes_the_member_off_the_imported_module() -> None:
    facts: dict[str, list[Fact]] = {
        APP: [Import(module="src", level=0, name="lib", alias=None, line=1)],
        LIB: [Defines(kind="class", name="Bar", parent=None, line=1)],
    }

    assert lookup(facts, "lib.Bar") == f"{LIB}::Bar#class"


def test_a_nested_declaration_is_found_by_its_full_path() -> None:
    facts: dict[str, list[Fact]] = {
        APP: [
            Defines(kind="class", name="Outer", parent=None, line=1),
            Defines(kind="class", name="Inner", parent="Outer", line=2),
        ]
    }

    assert lookup(facts, "Outer.Inner") == f"{APP}::Outer.Inner#class"
    # 裸名查不到——那要作用域感知，是 plan 5.5 的事
    assert lookup(facts, "Inner") is None


def test_a_module_bound_by_a_plain_import_is_not_a_declaration() -> None:
    facts: dict[str, list[Fact]] = {
        APP: [Import(module="src.lib", level=0, name=None, alias=None, line=1)]
    }

    assert lookup(facts, "src.lib") is None


def test_a_name_that_was_never_imported_is_not_found_anywhere() -> None:
    """另一個檔案有同名的 class 也不算——沒 import 就不在這個檔案的作用域裡。"""
    facts: dict[str, list[Fact]] = {
        APP: [Defines(kind="function", name="other", parent=None, line=1)],
        LIB: [Defines(kind="class", name="Bar", parent=None, line=1)],
    }

    assert lookup(facts, "Bar") is None


def test_an_external_package_has_nothing_to_look_inside() -> None:
    facts: dict[str, list[Fact]] = {
        APP: [Import(module="pydantic", level=0, name="BaseModel", alias=None, line=1)]
    }

    assert lookup(facts, "BaseModel") is None


def test_a_relative_import_uses_the_same_rules_as_imports_edges() -> None:
    facts: dict[str, list[Fact]] = {
        "file:src/pkg/thing.py": [
            Import(module=None, level=2, name="lib", alias=None, line=1)
        ],
        LIB: [Defines(kind="class", name="Bar", parent=None, line=1)],
    }

    assert (
        lookup(facts, "lib.Bar", where="file:src/pkg/thing.py") == f"{LIB}::Bar#class"
    )


def test_the_later_binding_wins_like_python_itself() -> None:
    facts: dict[str, list[Fact]] = {
        APP: [
            Defines(kind="class", name="Bar", parent=None, line=1),
            Defines(kind="function", name="Bar", parent=None, line=5),
        ]
    }

    assert lookup(facts, "Bar") == f"{APP}::Bar#function"
