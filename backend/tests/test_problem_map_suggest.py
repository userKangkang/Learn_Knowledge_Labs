import json

from fastapi.testclient import TestClient

from app.services.llm_gateway import StreamChunk


def _graph(client: TestClient) -> str:
    return client.post("/api/v1/graphs", json={"title": "G"}).json()["id"]


def _make_study_and_card(
    client: TestClient,
    monkeypatch,
    graph_id: str,
    *,
    selected: bool = False,
) -> tuple[str, str]:
    study_id = client.post(f"/api/v1/graphs/{graph_id}/paper-studies", json={"title": "P"}).json()["id"]
    monkeypatch.setattr("app.services.paper_study.documents.extract_pdf_text", lambda *_: "PRIMARY PAPER TEXT")
    client.post(
        f"/api/v1/paper-studies/{study_id}/document",
        files={"file": ("paper.pdf", b"dummy", "application/pdf")},
    )
    stream = lambda _self, **_kwargs: iter([StreamChunk(content_delta="AI")])  # noqa: E731
    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", stream)
    client.post(f"/api/v1/paper-studies/{study_id}/conversations/OVERVIEW/start")
    client.post(
        f"/api/v1/paper-studies/{study_id}/conversations/messages",
        json={"stage": "OVERVIEW", "content": "为什么？"},
    )
    client.patch(
        f"/api/v1/paper-studies/{study_id}/overview",
        json={
            "research_context": "训练系统",
            "core_problem": "资源错配",
            "main_approach": "解耦任务",
            "claimed_effect": "降低等待",
            "user_understanding": "暂定理解",
            "user_status": "CONFIRMED",
        },
    )
    client.post(f"/api/v1/paper-studies/{study_id}/conversations/PROBLEM_MAP/start")
    client.post(
        f"/api/v1/paper-studies/{study_id}/conversations/messages",
        json={"stage": "PROBLEM_MAP", "content": "有哪些问题？"},
    )
    card = client.post(
        f"/api/v1/paper-studies/{study_id}/problem-cards",
        json={"title": "卡"},
    ).json()
    if selected:
        client.patch(f"/api/v1/paper-problem-cards/{card['id']}", json={"selected": True})
    return study_id, card["id"]


def _mock_llm_json(monkeypatch, payload: dict) -> None:
    monkeypatch.setattr(
        "app.services.llm_gateway.LLMGateway.stream",
        lambda _self, **_kwargs: iter([StreamChunk(content_delta=json.dumps(payload, ensure_ascii=False))]),
    )


def test_suggest_requires_confirmed_cards(client: TestClient, monkeypatch) -> None:
    graph_id = _graph(client)
    _mock_llm_json(monkeypatch, {"problems": []})
    resp = client.post(f"/api/v1/graphs/{graph_id}/problem-map/suggest")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "NO_CONFIRMED_CARDS"


def test_suggest_parses_llm_json(client: TestClient, monkeypatch) -> None:
    graph_id = _graph(client)
    _, card_a = _make_study_and_card(client, monkeypatch, graph_id, selected=True)
    _, card_b = _make_study_and_card(client, monkeypatch, graph_id)
    _mock_llm_json(
        monkeypatch,
        {
            "note": "两篇论文都指向训练效率问题",
            "problems": [
                {"key": "p1", "title": "长尾环境训练效率", "description": "慢任务拖慢批次"},
                {"key": "p2", "title": "低资源场景下的部署", "parent_key": "p1"},
            ],
            "edges": [{"source_ref": "p1", "target_ref": "p2", "relation_label": "在低资源场景下"}],
            "card_links": [
                {"problem_card_id": card_a, "problem_ref": "p1", "link_type": "CORE"},
                {"problem_card_id": card_b, "problem_ref": "p1", "link_type": "TOUCHED"},
            ],
        },
    )

    resp = client.post(f"/api/v1/graphs/{graph_id}/problem-map/suggest")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["note"] == "两篇论文都指向训练效率问题"
    assert len(body["problems"]) == 2
    assert body["problems"][1]["parent_key"] == "p1"
    assert body["edges"][0]["relation_label"] == "在低资源场景下"
    assert {item["problem_card_id"] for item in body["card_links"]} == {card_a, card_b}
    # 未落库：导图仍为空
    assert client.get(f"/api/v1/graphs/{graph_id}/problem-map").json()["problems"] == []


def test_suggest_filters_invalid_refs_and_bad_json(client: TestClient, monkeypatch) -> None:
    graph_id = _graph(client)
    _, card_a = _make_study_and_card(client, monkeypatch, graph_id)
    _mock_llm_json(
        monkeypatch,
        {
            "problems": [{"key": "p1", "title": "有效问题"}, {"key": "p1", "title": "重复key被过滤"}],
            "edges": [{"source_ref": "p1", "target_ref": "missing", "relation_label": "细分"}],
            "card_links": [{"problem_card_id": card_a, "problem_ref": "missing", "link_type": "CORE"}],
        },
    )
    resp = client.post(f"/api/v1/graphs/{graph_id}/problem-map/suggest")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["problems"]) == 1
    assert body["edges"] == []
    assert body["card_links"] == []

    monkeypatch.setattr(
        "app.services.llm_gateway.LLMGateway.stream",
        lambda _self, **_kwargs: iter([StreamChunk(content_delta="抱歉，我无法返回 JSON")]),
    )
    resp = client.post(f"/api/v1/graphs/{graph_id}/problem-map/suggest")
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "LLM_JSON_INVALID"


def test_apply_creates_problems_edges_links(client: TestClient, monkeypatch) -> None:
    graph_id = _graph(client)
    _, card_a = _make_study_and_card(client, monkeypatch, graph_id, selected=True)
    _, card_b = _make_study_and_card(client, monkeypatch, graph_id)

    resp = client.post(
        f"/api/v1/graphs/{graph_id}/problem-map/apply",
        json={
            "problems": [
                {"key": "p1", "title": "长尾环境训练效率", "description": "慢任务拖慢批次"},
                {"key": "p2", "title": "低资源部署"},
            ],
            "edges": [{"source_ref": "p1", "target_ref": "p2", "relation_label": "在低资源场景下"}],
            "card_links": [
                {"problem_card_id": card_a, "problem_ref": "p1", "link_type": "CORE"},
                {"problem_card_id": card_b, "problem_ref": "p1", "link_type": "TOUCHED"},
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"created_problems": 2, "created_edges": 1, "created_links": 2}

    bundle = client.get(f"/api/v1/graphs/{graph_id}/problem-map").json()
    assert len(bundle["problems"]) == 2
    assert len(bundle["edges"]) == 1
    assert len(bundle["links"]) == 2
    root = next(problem for problem in bundle["problems"] if problem["title"] == "长尾环境训练效率")
    assert root["coverage_paper_count"] == 2
    assert root["coverage_core_count"] == 1
    assert root["coverage_touched_count"] == 1


def test_apply_reuses_existing_problem(client: TestClient, monkeypatch) -> None:
    graph_id = _graph(client)
    existing = client.post(f"/api/v1/graphs/{graph_id}/problems", json={"title": "已有问题"}).json()
    _, card_a = _make_study_and_card(client, monkeypatch, graph_id)

    resp = client.post(
        f"/api/v1/graphs/{graph_id}/problem-map/apply",
        json={
            "problems": [{"key": "p1", "title": "新子问题"}],
            "edges": [{"source_ref": existing["id"], "target_ref": "p1"}],
            "card_links": [{"problem_card_id": card_a, "problem_ref": existing["id"], "link_type": "TOUCHED"}],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"created_problems": 1, "created_edges": 1, "created_links": 1}
    bundle = client.get(f"/api/v1/graphs/{graph_id}/problem-map").json()
    assert len(bundle["problems"]) == 2
    assert bundle["links"][0]["shared_problem_id"] == existing["id"]


def test_apply_validations_and_rollback(client: TestClient, monkeypatch) -> None:
    graph_id = _graph(client)
    _, card_a = _make_study_and_card(client, monkeypatch, graph_id)

    base = {
        "problems": [{"key": "p1", "title": "问题A"}, {"key": "p1", "title": "问题B"}],
        "edges": [],
        "card_links": [],
    }
    dup_key = client.post(f"/api/v1/graphs/{graph_id}/problem-map/apply", json=base)
    assert dup_key.status_code == 400
    assert dup_key.json()["error"]["code"] == "APPLY_DUPLICATE_KEY"

    bad_ref = client.post(
        f"/api/v1/graphs/{graph_id}/problem-map/apply",
        json={
            "problems": [{"key": "p1", "title": "问题A"}],
            "edges": [],
            "card_links": [{"problem_card_id": card_a, "problem_ref": "ghost", "link_type": "CORE"}],
        },
    )
    assert bad_ref.status_code == 404
    assert bad_ref.json()["error"]["code"] == "APPLY_PROBLEM_REF_NOT_FOUND"
    # 失败请求不落任何数据
    assert client.get(f"/api/v1/graphs/{graph_id}/problem-map").json()["problems"] == []

    other_graph = _graph(client)
    _, other_card = _make_study_and_card(client, monkeypatch, other_graph)
    cross = client.post(
        f"/api/v1/graphs/{graph_id}/problem-map/apply",
        json={
            "problems": [{"key": "p1", "title": "问题A"}],
            "edges": [],
            "card_links": [{"problem_card_id": other_card, "problem_ref": "p1", "link_type": "TOUCHED"}],
        },
    )
    assert cross.status_code == 404
    assert cross.json()["error"]["code"] == "PAPER_PROBLEM_NOT_FOUND"

    ok = client.post(
        f"/api/v1/graphs/{graph_id}/problem-map/apply",
        json={
            "problems": [{"key": "p1", "title": "问题A"}],
            "edges": [],
            "card_links": [{"problem_card_id": card_a, "problem_ref": "p1", "link_type": "CORE"}],
        },
    )
    assert ok.status_code == 200
    created_id = client.get(f"/api/v1/graphs/{graph_id}/problem-map").json()["problems"][0]["id"]

    again = client.post(
        f"/api/v1/graphs/{graph_id}/problem-map/apply",
        json={
            "problems": [],
            "edges": [],
            "card_links": [{"problem_card_id": card_a, "problem_ref": created_id, "link_type": "TOUCHED"}],
        },
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "DUPLICATE_CARD_LINK"
