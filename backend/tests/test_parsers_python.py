from textwrap import dedent

from app.parsers import Import, PythonParser


def parse(source: str) -> tuple[Import, ...]:
    result = PythonParser().parse(dedent(source))

    assert result.error is None
    return result.facts


def test_plain_import_has_no_name_taken_out_of_it() -> None:
    assert parse("import x") == (
        Import(module="x", level=0, name=None, alias=None, line=1),
    )


def test_dotted_import_keeps_the_full_path_and_the_alias() -> None:
    assert parse("import a.b.c as abc") == (
        Import(module="a.b.c", level=0, name=None, alias="abc", line=1),
    )


def test_from_import_splits_into_module_and_name() -> None:
    assert parse("from foo import bar") == (
        Import(module="foo", level=0, name="bar", alias=None, line=1),
    )


def test_parenthesised_import_across_lines_yields_every_name() -> None:
    facts = parse(
        """
        from foo import (bar,
                         baz)
        """
    )

    assert [fact.name for fact in facts] == ["bar", "baz"]


def test_same_level_relative_import_has_no_module() -> None:
    assert parse("from . import sibling") == (
        Import(module=None, level=1, name="sibling", alias=None, line=1),
    )


def test_parent_level_relative_import_records_the_depth() -> None:
    assert parse("from ..pkg import deep") == (
        Import(module="pkg", level=2, name="deep", alias=None, line=1),
    )


def test_imports_inside_comments_and_strings_are_not_picked_up() -> None:
    facts = parse(
        """
        # import fake_comment
        sql = "import fake_string"
        '''
        from fake import docstring
        '''
        """
    )

    assert facts == ()


def test_imports_nested_in_blocks_are_picked_up() -> None:
    facts = parse(
        """
        if TYPE_CHECKING:
            import lazy_dep

        def f():
            import inside_function
        """
    )

    assert {fact.module for fact in facts} == {"lazy_dep", "inside_function"}


def test_facts_carry_line_numbers_and_come_out_in_source_order() -> None:
    facts = parse(
        """
        import first

        import second
        """
    )

    # 來源字串的第 1 行是 dedent 前的換行，所以 import 落在第 2 與第 4 行
    assert [(fact.module, fact.line) for fact in facts] == [("first", 2), ("second", 4)]


def test_a_file_without_imports_succeeds_with_nothing_in_it() -> None:
    result = PythonParser().parse("# 只有註解\n")

    assert result.facts == ()
    assert result.error is None


def test_syntax_error_loses_the_whole_file_but_says_so() -> None:
    result = PythonParser().parse("import x\ndef broken(:\n")

    assert result.facts == ()
    assert result.error is not None
    assert "line 2" in result.error


def test_binary_content_is_reported_as_a_failure_not_a_crash() -> None:
    result = PythonParser().parse("import x\n\x00")

    assert result.facts == ()
    assert result.error is not None
