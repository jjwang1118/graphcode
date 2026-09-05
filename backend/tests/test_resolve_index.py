from app.resolve import from_files

FILES = [
    "backend/app/__init__.py",
    "backend/app/graph/__init__.py",
    "backend/app/graph/build.py",
    "backend/app/models/__init__.py",
    "backend/README.md",
    "external/CFRU/main.py",
    "external/CFRU/utils/fflow.py",
    "tools/app/models/__init__.py",
]


def test_a_file_is_registered_under_every_way_of_counting() -> None:
    index = from_files(["external/CFRU/utils/fflow.py"])

    assert set(index.by_module) == {
        "external.CFRU.utils.fflow",
        "CFRU.utils.fflow",
        "utils.fflow",
        "fflow",
    }


def test_init_file_stands_for_its_directory() -> None:
    index = from_files(["backend/app/graph/__init__.py"])

    # 不是 backend.app.graph.__init__——__init__.py 自己不佔一段
    assert set(index.by_module) == {"backend.app.graph", "app.graph", "graph"}


def test_non_python_files_are_not_indexed() -> None:
    index = from_files(["backend/README.md"])

    assert index.by_module == {}
    assert index.files == frozenset()


def test_lookup_returns_the_only_match_without_marking_it() -> None:
    found = from_files(FILES).lookup("app.graph.build", "file:backend/app/__init__.py")

    assert found is not None
    assert found.target == "file:backend/app/graph/build.py"
    assert found.ambiguous == ()


def test_lookup_misses_a_name_nobody_registered() -> None:
    assert from_files(FILES).lookup("fastapi", "file:backend/app/__init__.py") is None


def test_collision_picks_the_nearest_and_records_every_candidate() -> None:
    found = from_files(FILES).lookup("app.models", "file:backend/app/graph/build.py")

    assert found is not None
    # backend/ 那個共用兩層目錄，tools/ 那個共用零層
    assert found.target == "file:backend/app/models/__init__.py"
    assert found.ambiguous == (
        "file:backend/app/models/__init__.py",
        "file:tools/app/models/__init__.py",
    )


def test_a_tie_falls_back_to_sort_order_so_the_graph_is_reproducible() -> None:
    index = from_files(["x/utils.py", "y/utils.py"])

    found = index.lookup("utils", "file:elsewhere/main.py")

    assert found is not None
    assert found.target == "file:x/utils.py"
    assert len(found.ambiguous) == 2


def test_at_path_finds_both_a_module_and_a_package() -> None:
    index = from_files(FILES)

    assert index.at_path("backend/app/graph/build") == "file:backend/app/graph/build.py"
    assert index.at_path("backend/app/graph") == "file:backend/app/graph/__init__.py"


def test_at_path_rejects_an_empty_path() -> None:
    assert from_files(FILES).at_path("") is None
