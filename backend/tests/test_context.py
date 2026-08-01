from fastapi.testclient import TestClient


def _setup_tree(client: TestClient) -> dict[str, str]:
    graph_id = client.post("/api/v1/graphs", json={"title": "G"}).json()["id"]
    gp = client.post(f"/api/v1/graphs/{graph_id}/nodes", json={"title": "GP"}).json()["id"]
    p = client.post(f"/api/v1/graphs/{graph_id}/nodes", json={"title": "P"}).json()["id"]
    a = client.post(f"/api/v1/graphs/{graph_id}/nodes", json={"title": "A"}).json()["id"]
    b = client.post(f"/api/v1/graphs/{graph_id}/nodes", json={"title": "B"}).json()["id"]
    client.post(
        f"/api/v1/graphs/{graph_id}/edges",
        json={"source_node_id": gp, "target_node_id": p, "type": "PREREQUISITE_OF"},
    )
    client.post(
        f"/api/v1/graphs/{graph_id}/edges",
        json={"source_node_id": p, "target_node_id": a, "type": "PREREQUISITE_OF"},
    )
    client.post(
        f"/api/v1/graphs/{graph_id}/edges",
        json={"source_node_id": p, "target_node_id": b, "type": "PREREQUISITE_OF"},
    )
    return {"graph_id": graph_id, "gp": gp, "p": p, "a": a, "b": b}


def test_session_policy_always_includes_current_history(client: TestClient) -> None:
    ids = _setup_tree(client)
    session_a = client.post(f"/api/v1/nodes/{ids['a']}/sessions", json={}).json()["id"]
    session_b = client.post(f"/api/v1/nodes/{ids['b']}/sessions", json={}).json()["id"]
    client.post(
        f"/api/v1/sessions/{session_a}/messages",
        json={"role": "USER", "content": "A-specific"},
    )
    client.post(
        f"/api/v1/sessions/{session_b}/messages",
        json={"role": "USER", "content": "B-current-history"},
    )

    policy = client.get(f"/api/v1/sessions/{session_b}/context-policy").json()
    assert policy["session_id"] == session_b
    assert policy["include_current_node_summary"] is False
    assert policy["include_current_session_history"] is True
    assert policy["sources"] == []

    preview = client.post(
        f"/api/v1/sessions/{session_b}/context-preview",
        json={"new_user_message": "hello"},
    ).json()
    assert "A-specific" not in preview["rendered_context"]
    assert "B-current-history" in preview["rendered_context"]
    assert "hello" in preview["rendered_context"]


def test_borrow_ancestor_and_non_ancestor_limit(client: TestClient) -> None:
    ids = _setup_tree(client)
    client.post(f"/api/v1/nodes/{ids['p']}/summary", json={"content": "父节点摘要内容"})
    session_b = client.post(f"/api/v1/nodes/{ids['b']}/sessions", json={}).json()["id"]
    session_a = client.post(f"/api/v1/nodes/{ids['a']}/sessions", json={}).json()["id"]
    client.post(
        f"/api/v1/sessions/{session_a}/messages",
        json={"role": "USER", "content": "A-talk"},
    )

    candidates = client.get(f"/api/v1/sessions/{session_b}/context-candidates").json()
    assert {c["id"] for c in candidates["ancestors"]} == {ids["p"], ids["gp"]}
    assert {c["id"] for c in candidates["non_ancestors"]} == {ids["a"]}

    ok = client.put(
        f"/api/v1/sessions/{session_b}/context-policy",
        json={
            "include_current_node_summary": False,
            "sources": [
                {
                    "source_node_id": ids["p"],
                    "include_summary": True,
                    "order_index": 0,
                    "sessions": [],
                },
                {
                    "source_node_id": ids["a"],
                    "include_summary": False,
                    "order_index": 1,
                    "sessions": [
                        {
                            "source_session_id": session_a,
                            "conversation_mode": "FULL_SESSION",
                            "order_index": 0,
                        }
                    ],
                },
            ],
        },
    )
    assert ok.status_code == 200

    preview = client.post(
        f"/api/v1/sessions/{session_b}/context-preview",
        json={"new_user_message": "q"},
    ).json()
    assert "父节点摘要内容" in preview["rendered_context"]
    assert "A-talk" in preview["rendered_context"]

    c = client.post(f"/api/v1/graphs/{ids['graph_id']}/nodes", json={"title": "C"}).json()["id"]
    d = client.post(f"/api/v1/graphs/{ids['graph_id']}/nodes", json={"title": "D"}).json()["id"]
    sc = client.post(f"/api/v1/nodes/{c}/sessions", json={}).json()["id"]
    sd = client.post(f"/api/v1/nodes/{d}/sessions", json={}).json()["id"]

    limited = client.put(
        f"/api/v1/sessions/{session_b}/context-policy",
        json={
            "include_current_node_summary": False,
            "sources": [
                {
                    "source_node_id": ids["a"],
                    "include_summary": False,
                    "order_index": 0,
                    "sessions": [
                        {"source_session_id": session_a, "conversation_mode": "FULL_SESSION", "order_index": 0}
                    ],
                },
                {
                    "source_node_id": c,
                    "include_summary": False,
                    "order_index": 1,
                    "sessions": [{"source_session_id": sc, "conversation_mode": "FULL_SESSION", "order_index": 0}],
                },
                {
                    "source_node_id": d,
                    "include_summary": False,
                    "order_index": 2,
                    "sessions": [{"source_session_id": sd, "conversation_mode": "FULL_SESSION", "order_index": 0}],
                },
            ],
        },
    )
    assert limited.status_code == 400
    assert limited.json()["error"]["code"] == "NON_ANCESTOR_LIMIT"


def test_same_node_other_session_and_cannot_borrow_current(client: TestClient) -> None:
    ids = _setup_tree(client)
    s1 = client.post(f"/api/v1/nodes/{ids['b']}/sessions", json={"title": "旧会话"}).json()["id"]
    s2 = client.post(f"/api/v1/nodes/{ids['b']}/sessions", json={"title": "新会话"}).json()["id"]
    client.post(f"/api/v1/sessions/{s1}/messages", json={"role": "USER", "content": "旧会话内容"})
    client.post(f"/api/v1/nodes/{ids['p']}/summary", json={"content": "原始父摘要"})

    put = client.put(
        f"/api/v1/sessions/{s2}/context-policy",
        json={
            "include_current_node_summary": False,
            "sources": [
                {
                    "source_node_id": ids["b"],
                    "include_summary": False,
                    "order_index": 0,
                    "sessions": [
                        {"source_session_id": s1, "conversation_mode": "FULL_SESSION", "order_index": 0}
                    ],
                },
                {
                    "source_node_id": ids["p"],
                    "include_summary": True,
                    "order_index": 1,
                    "sessions": [],
                },
            ],
        },
    )
    assert put.status_code == 200

    preview = client.post(
        f"/api/v1/sessions/{s2}/context-preview",
        json={"new_user_message": "问一句", "persist": True},
    ).json()
    assert "旧会话内容" in preview["rendered_context"]
    assert "原始父摘要" in preview["rendered_context"]

    bad_current = client.put(
        f"/api/v1/sessions/{s2}/context-policy",
        json={
            "include_current_node_summary": False,
            "sources": [
                {
                    "source_node_id": ids["b"],
                    "include_summary": False,
                    "order_index": 0,
                    "sessions": [
                        {"source_session_id": s2, "conversation_mode": "FULL_SESSION", "order_index": 0}
                    ],
                }
            ],
        },
    )
    assert bad_current.status_code == 400
    assert bad_current.json()["error"]["code"] == "CANNOT_BORROW_CURRENT_SESSION"

    # policies are per-session: s1 remains default/empty sources
    policy_s1 = client.get(f"/api/v1/sessions/{s1}/context-policy").json()
    assert policy_s1["sources"] == []
