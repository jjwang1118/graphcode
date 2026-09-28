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
    facts: Mapping[str, Sequence[Fact]],
    written: str,
    where: str = APP,
    scope: str | None = None,
) -> str | None:
    found = index(facts).lookup(where, written, scope)
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
    # 裸名在頂層看不到；寫在 Outer 裡面才看得到
    assert lookup(facts, "Inner") is None
    assert lookup(facts, "Inner", scope="Outer") == f"{APP}::Outer.Inner#class"


# --- 作用域：由內往外（plan 5.5） -----------------------------------------------


def test_a_closure_sees_what_its_enclosing_function_declared() -> None:
    facts: dict[str, list[Fact]] = {
        APP: [
            Defines(kind="function", name="build", parent=None, line=1),
            Defines(kind="function", name="step", parent="build", line=2),
            Defines(kind="function", name="inner", parent="build", line=3),
        ]
    }

    assert lookup(facts, "step", scope="build.inner") == f"{APP}::build.step#function"


def test_a_method_does_not_see_its_own_class_members() -> None:
    """方法裡寫 `run()` 指的是頂層的 run——class body 只對直接寫在裡面的可見。"""
    facts: dict[str, list[Fact]] = {
        APP: [
            Defines(kind="function", name="run", parent=None, line=1),
            Defines(kind="class", name="Job", parent=None, line=3),
            Defines(kind="function", name="run", parent="Job", line=4),
            Defines(kind="function", name="helper", parent="Job", line=6),
        ]
    }

    assert lookup(facts, "run", scope="Job.helper") == f"{APP}::run#function"
    # 沒有頂層可退時就是查不到，不會落到同一個 class 的方法上
    assert lookup(facts, "helper", scope="Job.run") is None


def test_an_inner_declaration_shadows_an_outer_one() -> None:
    facts: dict[str, list[Fact]] = {
        APP: [
            Defines(kind="function", name="helper", parent=None, line=1),
            Defines(kind="function", name="build", parent=None, line=3),
            Defines(kind="function", name="helper", parent="build", line=4),
        ]
    }

    assert lookup(facts, "helper", scope="build") == f"{APP}::build.helper#function"
    assert lookup(facts, "helper") == f"{APP}::helper#function"


def test_an_import_is_still_found_from_inside_a_function() -> None:
    facts: dict[str, list[Fact]] = {
        APP: [
            Import(module="src.lib", level=0, name="Bar", alias=None, line=1),
            Defines(kind="function", name="build", parent=None, line=3),
        ],
        LIB: [Defines(kind="class", name="Bar", parent=None, line=1)],
    }

    assert lookup(facts, "Bar", scope="build") == f"{LIB}::Bar#class"


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


# --- 轉出：沿目標檔案自己的 import 往下追（plan 5.6） --------------------------

PKG = "file:src/pkg/__init__.py"
THING = "file:src/pkg/thing.py"


def test_a_name_passed_on_by_an_init_is_followed_to_its_declaration() -> None:
    """`from src.pkg import collapse`，而 pkg/__init__.py 只是轉出 thing.py 的。"""
    facts: dict[str, list[Fact]] = {
        APP: [Import(module="src.pkg", level=0, name="collapse", alias=None, line=1)],
        PKG: [Import(module="thing", level=1, name="collapse", alias=None, line=1)],
        THING: [Defines(kind="function", name="collapse", parent=None, line=1)],
    }

    assert lookup(facts, "collapse") == f"{THING}::collapse#function"


def test_a_renamed_pass_on_is_followed_by_the_original_name() -> None:
    facts: dict[str, list[Fact]] = {
        APP: [Import(module="src.pkg", level=0, name="fold", alias=None, line=1)],
        PKG: [Import(module="thing", level=1, name="collapse", alias="fold", line=1)],
        THING: [Defines(kind="function", name="collapse", parent=None, line=1)],
    }

    assert lookup(facts, "fold") == f"{THING}::collapse#function"


def test_passing_on_works_through_several_files_and_not_only_inits() -> None:
    # app → lib（一般檔案）→ pkg/__init__ → thing
    facts: dict[str, list[Fact]] = {
        APP: [Import(module="src.lib", level=0, name="collapse", alias=None, line=1)],
        LIB: [Import(module="src.pkg", level=0, name="collapse", alias=None, line=1)],
        PKG: [Import(module="thing", level=1, name="collapse", alias=None, line=1)],
        THING: [Defines(kind="function", name="collapse", parent=None, line=1)],
    }

    assert lookup(facts, "collapse") == f"{THING}::collapse#function"


def test_files_pointing_at_each_other_stop_instead_of_looping() -> None:
    facts: dict[str, list[Fact]] = {
        APP: [Import(module="src.lib", level=0, name="ghost", alias=None, line=1)],
        LIB: [Import(module="src.pkg", level=0, name="ghost", alias=None, line=1)],
        PKG: [Import(module="src.lib", level=0, name="ghost", alias=None, line=1)],
    }

    assert lookup(facts, "ghost") is None


def test_a_dotted_name_through_a_package_follows_the_pass_on() -> None:
    # `import src.pkg` 之後寫 `src.pkg.collapse()`
    facts: dict[str, list[Fact]] = {
        APP: [Import(module="src.pkg", level=0, name=None, alias=None, line=1)],
        PKG: [Import(module="thing", level=1, name="collapse", alias=None, line=1)],
        THING: [Defines(kind="function", name="collapse", parent=None, line=1)],
    }

    assert lookup(facts, "src.pkg.collapse") == f"{THING}::collapse#function"
