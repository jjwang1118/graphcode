import json

import pytest
from pydantic import ValidationError

from app.models import Edge, EdgeType, GraphDocument, Meta, Node, NodeType


def _sample() -> GraphDocument:
    return GraphDocument(
        nodes=[
            Node(id="file:src/app.py", type=NodeType.FILE, label="app.py"),
            Node(
                id="file:src/utils/io.py",
                type=NodeType.FILE,
                label="io.py",
                properties={"lines": 12},
            ),
        ],
        edges=[
            Edge(
                source="file:src/app.py",
                target="file:src/utils/io.py",
                type=EdgeType.IMPORTS,
            )
        ],
        meta=Meta(node_count=2, edge_count=1),
    )


def test_empty_document_is_valid() -> None:
    doc = GraphDocument()
    assert doc.nodes == []
    assert doc.edges == []
    assert doc.meta == Meta()


def test_json_has_exactly_the_contracted_keys() -> None:
    payload = json.loads(_sample().model_dump_json())

    assert set(payload) == {"nodes", "edges", "meta"}
    assert set(payload["nodes"][0]) == {"id", "type", "label", "properties"}
    assert set(payload["edges"][0]) == {"source", "target", "type", "properties"}
    # 改這裡就要同步改 frontend/src/api/types.ts，否則前端靜默拿到 undefined
    assert set(payload["meta"]) == {
        "node_count",
        "edge_count",
        "cycles",
        "isolated_nodes",
        "parse_failures",
        "ambiguous_imports",
        "unresolved_imports",
        "analyzed_at",
    }


def test_type_serializes_as_a_plain_string() -> None:
    payload = json.loads(_sample().model_dump_json())

    assert payload["nodes"][0]["type"] == "file"
    assert payload["edges"][0]["type"] == "imports"


def test_round_trip_through_json() -> None:
    doc = _sample()
    assert GraphDocument.model_validate_json(doc.model_dump_json()) == doc


def test_unknown_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Node(id="file:src/app.py", type="fille", label="app.py")


def test_properties_is_an_open_bag() -> None:
    node = Node(
        id="file:src/app.py",
        type=NodeType.FILE,
        label="app.py",
        properties={"lines": 12, "language": "python"},
    )
    assert node.properties["language"] == "python"
