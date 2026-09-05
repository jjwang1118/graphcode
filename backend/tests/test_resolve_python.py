from app.models import EdgeType, NodeType
from app.parsers import Import
from app.resolve import PythonResolver, from_files, to_edges

FILES = [
    "backend/app/__init__.py",
    "backend/app/api/__init__.py",
    "backend/app/api/analyze.py",
    "backend/app/graph/__init__.py",
    "backend/app/graph/build.py",
    "backend/app/graph/query.py",
    "backend/app/models/__init__.py",
    "external/CFRU/main.py",
    "external/CFRU/utils/fflow.py",
]

INDEX = from_files(FILES)
RESOLVER = PythonResolver()

ANALYZE = "file:backend/app/api/analyze.py"
BUILD = "file:backend/app/graph/build.py"


def target(fact: Import, importer: str = ANALYZE) -> str | None:
    found = RESOLVER.target(fact, importer, INDEX)
    return None if found is None else found.target


def an_import(
    module: str | None = None,
    level: int = 0,
    name: str | None = None,
    line: int = 1,
) -> Import:
    return Import(module=module, level=level, name=name, alias=None, line=line)


# ── 絕對 import ──────────────────────────────────────────────────


def test_a_project_module_resolves_to_its_file() -> None:
    assert target(an_import("app.graph.query")) == "file:backend/app/graph/query.py"


def test_a_submodule_is_tried_before_falling_back_to_the_package() -> None:
    # from app.graph import build —— build.py 存在，指它比指 __init__.py 有用
    assert target(an_import("app.graph", name="build")) == BUILD


def test_a_name_that_is_not_a_submodule_falls_back_to_the_package() -> None:
    # BuildError 是 __init__.py 轉出來的名字，沒有 BuildError.py
    assert (
        target(an_import("app.graph", name="BuildError"))
        == "file:backend/app/graph/__init__.py"
    )


def test_star_import_falls_back_to_the_package() -> None:
    assert (
        target(an_import("app.models", name="*"))
        == "file:backend/app/models/__init__.py"
    )


def test_a_shallow_name_still_resolves_without_any_init_file() -> None:
    # external/CFRU/ 底下沒有 __init__.py，但 main.py 確實寫 import utils.fflow
    importer = "file:external/CFRU/main.py"

    assert (
        target(an_import("utils.fflow"), importer)
        == "file:external/CFRU/utils/fflow.py"
    )


# ── 外部套件 ─────────────────────────────────────────────────────


def test_an_unknown_name_becomes_an_external_package() -> None:
    assert target(an_import("fastapi", name="APIRouter")) == "ext:fastapi"


def test_an_external_package_is_named_by_its_top_level_only() -> None:
    assert target(an_import("fastapi.routing", name="APIRoute")) == "ext:fastapi"


# ── 相對 import ──────────────────────────────────────────────────


def test_same_level_relative_import_looks_next_door() -> None:
    assert target(an_import(level=1, name="query"), BUILD) == (
        "file:backend/app/graph/query.py"
    )


def test_same_level_relative_import_can_land_on_the_package_itself() -> None:
    assert target(an_import(level=1, name="missing"), BUILD) == (
        "file:backend/app/graph/__init__.py"
    )


def test_parent_level_relative_import_climbs_one_directory() -> None:
    assert target(an_import("models", level=2, name="Node"), BUILD) == (
        "file:backend/app/models/__init__.py"
    )


def test_a_relative_import_that_climbs_out_of_the_project_resolves_to_nothing() -> None:
    # from ...... import x —— Python 自己也不允許，不該硬造外部套件節點
    assert target(an_import(level=6, name="x"), BUILD) is None


# ── 接成邊 ───────────────────────────────────────────────────────


def test_every_fact_becomes_its_own_edge() -> None:
    facts = {
        ANALYZE: [
            an_import("app.graph", name="BuildError", line=11),
            an_import("app.graph", name="build", line=11),
            an_import("fastapi", name="APIRouter", line=8),
        ]
    }

    result = to_edges(facts, INDEX, RESOLVER)

    assert len(result.edges) == 3
    assert {edge.type for edge in result.edges} == {EdgeType.IMPORTS}
    assert all(edge.source == ANALYZE for edge in result.edges)


def test_an_edge_keeps_what_was_written_in_the_source() -> None:
    facts = {ANALYZE: [an_import("fastapi.routing", name="APIRoute", line=8)]}

    edge = to_edges(facts, INDEX, RESOLVER).edges[0]

    assert edge.target == "ext:fastapi"
    # 節點只留最頂層，完整路徑留在這裡，資訊沒丟
    assert edge.properties == {
        "module": "fastapi.routing",
        "name": "APIRoute",
        "line": 8,
    }


def test_a_relative_import_records_the_dots_it_was_written_with() -> None:
    facts = {BUILD: [an_import("models", level=2, name="Node", line=3)]}

    edge = to_edges(facts, INDEX, RESOLVER).edges[0]

    assert edge.properties["module"] == "..models"


def test_external_packages_become_nodes_once_each() -> None:
    facts = {
        ANALYZE: [
            an_import("fastapi", name="APIRouter"),
            an_import("fastapi", name="HTTPException"),
            an_import("pydantic", name="BaseModel"),
        ]
    }

    result = to_edges(facts, INDEX, RESOLVER)

    assert [node.id for node in result.nodes] == ["ext:fastapi", "ext:pydantic"]
    assert {node.type for node in result.nodes} == {NodeType.EXTERNAL_PACKAGE}
    assert [node.label for node in result.nodes] == ["fastapi", "pydantic"]


def test_a_file_that_is_in_the_project_never_becomes_a_node_here() -> None:
    # 專案內的檔案節點是 scan 產的，resolve 不該重複產一份
    facts = {ANALYZE: [an_import("app.graph.query")]}

    assert to_edges(facts, INDEX, RESOLVER).nodes == ()


def test_unresolved_relative_imports_are_counted_not_hidden() -> None:
    facts = {BUILD: [an_import(level=6, name="x")]}

    result = to_edges(facts, INDEX, RESOLVER)

    assert result.edges == ()
    assert result.unresolved == 1


def test_ambiguous_edges_are_counted_and_carry_their_candidates() -> None:
    index = from_files(["x/utils.py", "y/utils.py", "elsewhere/main.py"])
    facts = {"file:elsewhere/main.py": [an_import("utils", name="helper")]}

    result = to_edges(facts, index, RESOLVER)

    assert result.ambiguous == 1
    assert result.edges[0].properties["ambiguous"] == [
        "file:x/utils.py",
        "file:y/utils.py",
    ]
