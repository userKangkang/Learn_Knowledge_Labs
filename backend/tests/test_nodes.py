from fastapi.testclient import TestClient


def _graph(client: TestClient) -> str:
    return client.post("/api/v1/graphs", json={"title": "G"}).json()["id"]


def test_node_crud_and_position(client: TestClient) -> None:
    graph_id = _graph(client)
    created = client.post(
        f"/api/v1/graphs/{graph_id}/nodes",
        json={"title": "Concept", "node_type": "CONCEPT", "position_x": 10, "position_y": 20},
    )
    assert created.status_code == 201
    node_id = created.json()["id"]

    moved = client.patch(f"/api/v1/nodes/{node_id}/position", json={"x": 100, "y": 200})
    assert moved.status_code == 200
    assert moved.json()["position_x"] == 100
    assert moved.json()["position_y"] == 200

    updated = client.patch(f"/api/v1/nodes/{node_id}", json={"title": "Updated"})
    assert updated.json()["title"] == "Updated"

    assert client.delete(f"/api/v1/nodes/{node_id}").status_code == 204
    assert client.get(f"/api/v1/nodes/{node_id}").status_code == 404


def test_cannot_delete_node_with_edges(client: TestClient) -> None:
    graph_id = _graph(client)
    a = client.post(f"/api/v1/graphs/{graph_id}/nodes", json={"title": "A"}).json()["id"]
    b = client.post(f"/api/v1/graphs/{graph_id}/nodes", json={"title": "B"}).json()["id"]
    client.post(
        f"/api/v1/graphs/{graph_id}/edges",
        json={"source_node_id": a, "target_node_id": b, "type": "PART_OF"},
    )

    response = client.delete(f"/api/v1/nodes/{a}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NODE_HAS_EDGES"
