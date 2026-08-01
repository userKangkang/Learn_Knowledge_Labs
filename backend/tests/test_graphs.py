from fastapi.testclient import TestClient


def test_create_list_and_soft_delete_graph(client: TestClient) -> None:
    create = client.post("/api/v1/graphs", json={"title": "Algo", "description": "dsa"})
    assert create.status_code == 201
    graph_id = create.json()["id"]

    listed = client.get("/api/v1/graphs")
    assert listed.status_code == 200
    assert any(item["id"] == graph_id for item in listed.json())

    deleted = client.delete(f"/api/v1/graphs/{graph_id}")
    assert deleted.status_code == 204

    listed_after = client.get("/api/v1/graphs")
    assert all(item["id"] != graph_id for item in listed_after.json())


def test_delete_graph_cascades_nodes_and_edges(client: TestClient) -> None:
    graph_id = client.post("/api/v1/graphs", json={"title": "Cascade"}).json()["id"]
    n1 = client.post(f"/api/v1/graphs/{graph_id}/nodes", json={"title": "A"}).json()["id"]
    n2 = client.post(f"/api/v1/graphs/{graph_id}/nodes", json={"title": "B"}).json()["id"]
    client.post(
        f"/api/v1/graphs/{graph_id}/edges",
        json={"source_node_id": n1, "target_node_id": n2, "type": "IS_A"},
    )

    assert client.delete(f"/api/v1/graphs/{graph_id}").status_code == 204
    assert client.get(f"/api/v1/graphs/{graph_id}/nodes").status_code == 404
    assert client.get(f"/api/v1/nodes/{n1}").status_code == 404
