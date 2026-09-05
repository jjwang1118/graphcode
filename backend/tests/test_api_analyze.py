from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.analyze import AnalyzeRequest, analyze
from app.ingest import ALLOWED_ROOTS_ENV
from app.main import app
from app.models import EdgeType


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path.resolve() / "project"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("")
    monkeypatch.setenv(ALLOWED_ROOTS_ENV, str(root))
    return root


def test_analyze_returns_the_whole_graph(project: Path) -> None:
    document = analyze(AnalyzeRequest(path=str(project)))

    assert {node.id for node in document.nodes} == {
        "repo:.",
        "dir:src",
        "file:src/app.py",
    }
    assert document.meta.node_count == 3


def test_edge_types_selects_a_view(project: Path) -> None:
    document = analyze(AnalyzeRequest(path=str(project), edge_types=[EdgeType.IMPORTS]))

    # 階段 1 還沒有 imports 邊，但節點仍然全部在。
    assert document.edges == []
    assert len(document.nodes) == 3


def test_a_rejected_path_becomes_400(project: Path, tmp_path: Path) -> None:
    outside = tmp_path.resolve() / "outside"
    outside.mkdir()

    with pytest.raises(HTTPException) as error:
        analyze(AnalyzeRequest(path=str(outside)))

    assert error.value.status_code == 400


def test_the_error_body_leaks_neither_the_path_nor_the_allowlist(
    project: Path, tmp_path: Path
) -> None:
    outside = tmp_path.resolve() / "outside"
    outside.mkdir()

    with pytest.raises(HTTPException) as error:
        analyze(AnalyzeRequest(path=str(outside)))

    assert str(outside) not in str(error.value.detail)
    assert str(project) not in str(error.value.detail)


def test_openapi_declares_the_endpoint_and_its_response_model() -> None:
    schema = app.openapi()
    responses = schema["paths"]["/api/analyze"]["post"]["responses"]

    reference = responses["200"]["content"]["application/json"]["schema"]["$ref"]
    assert reference.endswith("/GraphDocument")
    assert "GraphDocument" in schema["components"]["schemas"]
