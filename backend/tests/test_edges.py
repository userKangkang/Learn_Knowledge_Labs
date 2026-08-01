from fastapi.testclient import TestClient


def _setup(client: TestClient) -> tuple[str, str, str]:
    graph_id = client.post("/api/v1/graphs", json={"title": "G"}).json()["id"]
    a = client.post(f"/api/v1/graphs/{graph_id}/nodes", json={"title": "A"}).json()["id"]
    b = client.post(f"/api/v1/graphs/{graph_id}/nodes", json={"title": "B"}).json()["id"]
    return graph_id, a, b


def test_create_typed_edge_and_forbid_self_loop(client: TestClient) -> None:
    graph_id, a, b = _setup(client)

    edge = client.post(
        f"/api/v1/graphs/{graph_id}/edges",
        json={"source_node_id": a, "target_node_id": b, "type": "PREREQUISITE_OF"},
    )
    assert edge.status_code == 201

    loop = client.post(
        f"/api/v1/graphs/{graph_id}/edges",
        json={"source_node_id": a, "target_node_id": a, "type": "IS_A"},
    )
    assert loop.status_code == 400
    assert loop.json()["error"]["code"] == "SELF_LOOP_FORBIDDEN"


def test_duplicate_edge_and_custom_label(client: TestClient) -> None:
    graph_id, a, b = _setup(client)

    first = client.post(
        f"/api/v1/graphs/{graph_id}/edges",
        json={"source_node_id": a, "target_node_id": b, "type": "IS_A"},
    )
    assert first.status_code == 201

    dup = client.post(
        f"/api/v1/graphs/{graph_id}/edges",
        json={"source_node_id": a, "target_node_id": b, "type": "IS_A"},
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "DUPLICATE_EDGE"

    custom_missing = client.post(
        f"/api/v1/graphs/{graph_id}/edges",
        json={"source_node_id": a, "target_node_id": b, "type": "CUSTOM"},
    )
    assert custom_missing.status_code == 400

    custom_ok = client.post(
        f"/api/v1/graphs/{graph_id}/edges",
        json={"source_node_id": a, "target_node_id": b, "type": "CUSTOM", "custom_label": "related"},
    )
    assert custom_ok.status_code == 201

    soft_deleted = client.delete(f"/api/v1/edges/{first.json()['id']}")
    assert soft_deleted.status_code == 204

    recreate = client.post(
        f"/api/v1/graphs/{graph_id}/edges",
        json={"source_node_id": a, "target_node_id": b, "type": "IS_A"},
    )
    assert recreate.status_code == 201


def test_reverse_edge_direction(client: TestClient) -> None:
    graph_id, a, b = _setup(client)
    created = client.post(
        f"/api/v1/graphs/{graph_id}/edges",
        json={"source_node_id": a, "target_node_id": b, "type": "PART_OF"},
    )
    assert created.status_code == 201
    edge_id = created.json()["id"]

    reversed_edge = client.patch(f"/api/v1/edges/{edge_id}", json={"reverse": True})
    assert reversed_edge.status_code == 200, reversed_edge.text
    body = reversed_edge.json()
    assert body["source_node_id"] == b
    assert body["target_node_id"] == a
    assert body["type"] == "PART_OF"

    again = client.patch(f"/api/v1/edges/{edge_id}", json={"reverse": True})
    assert again.status_code == 200
    assert again.json()["source_node_id"] == a
    assert again.json()["target_node_id"] == b
