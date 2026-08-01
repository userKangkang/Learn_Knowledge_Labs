from fastapi.testclient import TestClient


def _two_nodes(client: TestClient) -> tuple[str, str]:
    graph_id = client.post("/api/v1/graphs", json={"title": "G"}).json()["id"]
    a = client.post(f"/api/v1/graphs/{graph_id}/nodes", json={"title": "A"}).json()["id"]
    b = client.post(f"/api/v1/graphs/{graph_id}/nodes", json={"title": "B"}).json()["id"]
    return a, b


def test_session_and_message_isolation(client: TestClient) -> None:
    node_a, node_b = _two_nodes(client)

    sa1 = client.post(f"/api/v1/nodes/{node_a}/sessions", json={}).json()
    sa2 = client.post(f"/api/v1/nodes/{node_a}/sessions", json={"title": "专题讨论"}).json()
    sb1 = client.post(f"/api/v1/nodes/{node_b}/sessions", json={}).json()

    msg = client.post(
        f"/api/v1/sessions/{sa1['id']}/messages",
        json={"role": "USER", "content": "A-specific"},
    )
    assert msg.status_code == 201

    client.post(
        f"/api/v1/sessions/{sa2['id']}/messages",
        json={"role": "ASSISTANT", "content": "session-2-only"},
    )
    client.post(
        f"/api/v1/sessions/{sb1['id']}/messages",
        json={"role": "USER", "content": "B-specific"},
    )

    a1_messages = client.get(f"/api/v1/sessions/{sa1['id']}/messages").json()
    a2_messages = client.get(f"/api/v1/sessions/{sa2['id']}/messages").json()
    b1_messages = client.get(f"/api/v1/sessions/{sb1['id']}/messages").json()

    assert [m["content"] for m in a1_messages] == ["A-specific"]
    assert [m["content"] for m in a2_messages] == ["session-2-only"]
    assert [m["content"] for m in b1_messages] == ["B-specific"]

    sessions_a = client.get(f"/api/v1/nodes/{node_a}/sessions").json()
    assert {s["id"] for s in sessions_a} == {sa1["id"], sa2["id"]}


def test_message_revision_and_soft_delete(client: TestClient) -> None:
    node_a, _ = _two_nodes(client)
    session_id = client.post(f"/api/v1/nodes/{node_a}/sessions", json={}).json()["id"]
    created = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"role": "USER", "content": "原始内容"},
    ).json()

    edited = client.patch(f"/api/v1/messages/{created['id']}", json={"content": "修订内容"})
    assert edited.status_code == 200
    assert edited.json()["content"] == "修订内容"
    assert edited.json()["current_revision"] == 2
    assert edited.json()["status"] == "EDITED"

    revisions = client.get(f"/api/v1/messages/{created['id']}/revisions").json()
    assert [r["content"] for r in revisions] == ["原始内容", "修订内容"]

    assert client.delete(f"/api/v1/messages/{created['id']}").status_code == 204
    assert client.get(f"/api/v1/sessions/{session_id}/messages").json() == []

    forbidden = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"role": "SYSTEM", "content": "nope"},
    )
    assert forbidden.status_code == 400
