from fastapi.testclient import TestClient


def _node(client: TestClient) -> str:
    graph_id = client.post("/api/v1/graphs", json={"title": "G"}).json()["id"]
    return client.post(f"/api/v1/graphs/{graph_id}/nodes", json={"title": "N"}).json()["id"]


def test_summary_versions_and_activate(client: TestClient) -> None:
    node_id = _node(client)

    assert client.get(f"/api/v1/nodes/{node_id}/summary").json() is None

    v1 = client.post(f"/api/v1/nodes/{node_id}/summary", json={"content": "第一版摘要"})
    assert v1.status_code == 201
    assert v1.json()["version_number"] == 1
    assert v1.json()["is_current"] is True

    v2 = client.post(f"/api/v1/nodes/{node_id}/summary", json={"content": "第二版摘要"})
    assert v2.status_code == 201
    assert client.get(f"/api/v1/nodes/{node_id}/summary").json()["content"] == "第二版摘要"

    activated = client.post(f"/api/v1/nodes/{node_id}/summary/versions/{v1.json()['id']}/activate")
    assert activated.status_code == 200
    assert activated.json()["content"] == "第一版摘要"

    node = client.get(f"/api/v1/nodes/{node_id}").json()
    assert node["summary_preview"] == "第一版摘要"

    empty = client.post(f"/api/v1/nodes/{node_id}/summary", json={"content": "   "})
    assert empty.status_code == 400


def test_summary_update_and_soft_delete(client: TestClient) -> None:
    node_id = _node(client)
    v1 = client.post(f"/api/v1/nodes/{node_id}/summary", json={"content": "版本一"}).json()
    v2 = client.post(f"/api/v1/nodes/{node_id}/summary", json={"content": "版本二"}).json()

    updated = client.patch(
        f"/api/v1/nodes/{node_id}/summary/versions/{v1['id']}",
        json={"content": "版本一已修改"},
    )
    assert updated.status_code == 200
    assert updated.json()["content"] == "版本一已修改"
    assert updated.json()["is_current"] is False

    updated_current = client.patch(
        f"/api/v1/nodes/{node_id}/summary/versions/{v2['id']}",
        json={"content": "版本二已修改"},
    )
    assert updated_current.status_code == 200
    assert client.get(f"/api/v1/nodes/{node_id}/summary").json()["content"] == "版本二已修改"

    deleted = client.delete(f"/api/v1/nodes/{node_id}/summary/versions/{v2['id']}")
    assert deleted.status_code == 204

    # Deleting current falls back to latest remaining
    current = client.get(f"/api/v1/nodes/{node_id}/summary").json()
    assert current["id"] == v1["id"]
    assert current["content"] == "版本一已修改"

    versions = client.get(f"/api/v1/nodes/{node_id}/summary/versions").json()
    assert [v["id"] for v in versions] == [v1["id"]]

    assert client.delete(f"/api/v1/nodes/{node_id}/summary/versions/{v1['id']}").status_code == 204
    assert client.get(f"/api/v1/nodes/{node_id}/summary").json() is None
