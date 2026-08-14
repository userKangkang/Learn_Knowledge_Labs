from fastapi.testclient import TestClient

from app.config import get_settings
from app.services.llm_gateway import StreamChunk


def _setup(client: TestClient) -> tuple[str, str, str]:
    graph_id = client.post("/api/v1/graphs", json={"title": "G"}).json()["id"]
    a = client.post(f"/api/v1/graphs/{graph_id}/problems", json={"title": "大问题A"}).json()["id"]
    b = client.post(f"/api/v1/graphs/{graph_id}/problems", json={"title": "子问题B"}).json()["id"]
    return graph_id, a, b


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
    confirmed = client.patch(
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
    assert confirmed.status_code == 200, confirmed.text
    client.post(f"/api/v1/paper-studies/{study_id}/conversations/PROBLEM_MAP/start")
    client.post(
        f"/api/v1/paper-studies/{study_id}/conversations/messages",
        json={"stage": "PROBLEM_MAP", "content": "有哪些问题？"},
    )
    card = client.post(
        f"/api/v1/paper-studies/{study_id}/problem-cards",
        json={"title": "卡", "qualitative_overview": "这是一条用于画布展示的定性概述"},
    ).json()
    assert "id" in card, card
    if selected:
        client.patch(f"/api/v1/paper-problem-cards/{card['id']}", json={"selected": True})
    return study_id, card["id"]


def test_problem_crud_with_zero_coverage(client: TestClient) -> None:
    graph_id, a, _ = _setup(client)

    created = client.post(
        f"/api/v1/graphs/{graph_id}/problems",
        json={"title": "  新问题  ", "description": "描述"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["title"] == "新问题"
    assert body["coverage_paper_count"] == 0

    listed = client.get(f"/api/v1/graphs/{graph_id}/problems")
    assert listed.status_code == 200
    assert len(listed.json()) == 3

    detail = client.get(f"/api/v1/problems/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["description"] == "描述"

    updated = client.patch(f"/api/v1/problems/{body['id']}", json={"title": "改题名"})
    assert updated.status_code == 200
    assert updated.json()["title"] == "改题名"

    deleted = client.delete(f"/api/v1/problems/{body['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/problems/{body['id']}").status_code == 404
    assert a  # keep reference to avoid lint warnings


def test_related_paper_search_stream_uses_selected_overview_and_ccf_constraint(
    client: TestClient,
    monkeypatch,
) -> None:
    graph_id, _, _ = _setup(client)
    study_id, _ = _make_study_and_card(client, monkeypatch, graph_id)
    captured: dict = {}

    def fake_stream(_self, **kwargs):
        captured.update(kwargs)
        yield StreamChunk(content_delta="推荐论文 A")

    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", fake_stream)
    response = client.post(
        f"/api/v1/graphs/{graph_id}/problem-map/related-paper-search/stream",
        json={
            "study_ids": [study_id],
            "model": "deepseek-v4-flash",
            "prompt": "寻找处理同类资源错配问题的论文",
            "ccf_a_only": True,
            "prior_turns": [],
        },
    )

    assert response.status_code == 200, response.text
    assert "推荐论文 A" in response.text
    assert captured["provider"] == "deepseek"
    assert captured["web_search"] is True
    assert "研究场景：训练系统" in captured["system_prompt"]
    assert "核心问题：资源错配" in captured["system_prompt"]
    assert "主要方法：解耦任务" in captured["system_prompt"]
    assert "只纳入已在 CCF 推荐目录中列为 A 类" in captured["system_prompt"]
    assert captured["messages"][-1]["content"] == "寻找处理同类资源错配问题的论文"


def test_related_paper_search_kimi_uses_web_and_rejects_cross_graph_study(
    client: TestClient,
    monkeypatch,
) -> None:
    graph_id, _, _ = _setup(client)
    study_id, _ = _make_study_and_card(client, monkeypatch, graph_id)
    captured: dict = {}

    def fake_stream(_self, **kwargs):
        captured.update(kwargs)
        yield StreamChunk(content_delta="Kimi 推荐")

    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", fake_stream)
    response = client.post(
        f"/api/v1/graphs/{graph_id}/problem-map/related-paper-search/stream",
        json={
            "study_ids": [study_id],
            "model": "kimi-k3",
            "prompt": "给出相关工作",
            "ccf_a_only": False,
        },
    )
    assert response.status_code == 200, response.text
    assert "Kimi 推荐" in response.text
    assert captured["provider"] == "kimi"
    assert captured["web_search"] is True

    other_graph, _, _ = _setup(client)
    rejected = client.post(
        f"/api/v1/graphs/{other_graph}/problem-map/related-paper-search/stream",
        json={"study_ids": [study_id], "model": "deepseek-v4-flash", "prompt": "越权读取"},
    )
    assert rejected.status_code == 404


def test_related_paper_search_cancels_without_completing_partial_answer(
    client: TestClient,
    monkeypatch,
) -> None:
    graph_id, _, _ = _setup(client)
    study_id, _ = _make_study_and_card(client, monkeypatch, graph_id)
    cancel_checks = iter([False, True])

    def fake_stream(_self, **_kwargs):
        yield StreamChunk(content_delta="不完整回答")
        yield StreamChunk(content_delta="不应出现")

    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", fake_stream)
    monkeypatch.setattr(
        "app.services.cancel_registry.is_cancelled",
        lambda _request_id: next(cancel_checks, True),
    )
    response = client.post(
        f"/api/v1/graphs/{graph_id}/problem-map/related-paper-search/stream",
        json={
            "study_ids": [study_id],
            "model": "deepseek-v4-flash",
            "prompt": "寻找相关论文",
        },
    )

    assert response.status_code == 200
    assert "不完整回答" in response.text
    assert "不应出现" not in response.text
    assert "event: cancelled" in response.text
    assert "event: completed" not in response.text


def test_related_paper_search_applies_context_budget_and_reports_truncation(
    client: TestClient,
    monkeypatch,
) -> None:
    graph_id, _, _ = _setup(client)
    study_id, _ = _make_study_and_card(client, monkeypatch, graph_id)
    settings = get_settings()
    monkeypatch.setattr(settings, "related_paper_search_max_context_tokens", 1000)
    captured: dict = {}

    def fake_stream(_self, **kwargs):
        captured.update(kwargs)
        yield StreamChunk(content_delta="预算内回答")

    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", fake_stream)
    long_turns = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": "历史内容" * 1800}
        for index in range(8)
    ]
    response = client.post(
        f"/api/v1/graphs/{graph_id}/problem-map/related-paper-search/stream",
        json={
            "study_ids": [study_id],
            "model": "deepseek-v4-flash",
            "prompt": "寻找相关论文",
            "prior_turns": long_turns,
        },
    )

    assert response.status_code == 200, response.text
    assert '"truncated": true' in response.text
    assert '"estimated_input_tokens":' in response.text
    assert len(captured["messages"]) < len(long_turns) + 1
    assert captured["messages"][-1]["content"] == "寻找相关论文"


def test_problem_delete_blocked_by_edge_and_link(client: TestClient, monkeypatch) -> None:
    graph_id, a, b = _setup(client)

    edge = client.post(
        f"/api/v1/graphs/{graph_id}/problem-edges",
        json={"source_problem_id": a, "target_problem_id": b},
    ).json()
    blocked = client.delete(f"/api/v1/problems/{a}")
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "PROBLEM_HAS_EDGES"

    client.delete(f"/api/v1/problem-edges/{edge['id']}")

    _, card_id = _make_study_and_card(client, monkeypatch, graph_id)
    link = client.post(f"/api/v1/problem-cards/{card_id}/links", json={"shared_problem_id": a}).json()
    blocked = client.delete(f"/api/v1/problems/{a}")
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "PROBLEM_HAS_CARD_LINKS"

    client.delete(f"/api/v1/card-links/{link['id']}")
    assert client.delete(f"/api/v1/problems/{a}").status_code == 204


def test_problem_edge_rules(client: TestClient) -> None:
    graph_id, a, b = _setup(client)

    loop = client.post(
        f"/api/v1/graphs/{graph_id}/problem-edges",
        json={"source_problem_id": a, "target_problem_id": a},
    )
    assert loop.status_code == 400
    assert loop.json()["error"]["code"] == "SELF_LOOP_FORBIDDEN"

    created = client.post(
        f"/api/v1/graphs/{graph_id}/problem-edges",
        json={"source_problem_id": a, "target_problem_id": b, "relation_label": "在低资源场景下"},
    )
    assert created.status_code == 201
    edge_id = created.json()["id"]

    dup = client.post(
        f"/api/v1/graphs/{graph_id}/problem-edges",
        json={"source_problem_id": a, "target_problem_id": b, "relation_label": "在低资源场景下"},
    )
    assert dup.status_code == 409

    other_graph = client.post("/api/v1/graphs", json={"title": "Other"}).json()["id"]
    foreign = client.post(f"/api/v1/graphs/{other_graph}/problems", json={"title": "外部问题"}).json()["id"]
    cross = client.post(
        f"/api/v1/graphs/{graph_id}/problem-edges",
        json={"source_problem_id": a, "target_problem_id": foreign},
    )
    assert cross.status_code == 404

    reversed_edge = client.patch(f"/api/v1/problem-edges/{edge_id}", json={"reverse": True, "relation_label": "SPECIALIZES_INTO"})
    assert reversed_edge.status_code == 200
    body = reversed_edge.json()
    assert body["source_problem_id"] == b
    assert body["target_problem_id"] == a
    assert body["relation_label"] == "SPECIALIZES_INTO"

    assert client.delete(f"/api/v1/problem-edges/{edge_id}").status_code == 204
    assert client.patch(f"/api/v1/problem-edges/{edge_id}", json={"reverse": True}).status_code == 404


def test_card_link_default_type_and_rules(client: TestClient, monkeypatch) -> None:
    graph_id, a, _ = _setup(client)

    _, core_card = _make_study_and_card(client, monkeypatch, graph_id, selected=True)
    core_link = client.post(f"/api/v1/problem-cards/{core_card}/links", json={"shared_problem_id": a})
    assert core_link.status_code == 201
    assert core_link.json()["link_type"] == "CORE"

    _, touched_card = _make_study_and_card(client, monkeypatch, graph_id)
    touched_link = client.post(
        f"/api/v1/problem-cards/{touched_card}/links",
        json={"shared_problem_id": a, "link_type": "TOUCHED"},
    )
    assert touched_link.status_code == 201
    assert touched_link.json()["link_type"] == "TOUCHED"

    dup = client.post(f"/api/v1/problem-cards/{touched_card}/links", json={"shared_problem_id": a})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "DUPLICATE_CARD_LINK"

    link_id = touched_link.json()["id"]
    patched = client.patch(f"/api/v1/card-links/{link_id}", json={"link_type": "CORE"})
    assert patched.status_code == 200
    assert patched.json()["link_type"] == "CORE"

    listed = client.get(f"/api/v1/graphs/{graph_id}/card-links")
    assert listed.status_code == 200
    assert len(listed.json()) == 2

    assert client.delete(f"/api/v1/card-links/{link_id}").status_code == 204
    assert client.delete(f"/api/v1/card-links/{link_id}").status_code == 404
    assert core_link.json()["id"]  # keep reference


def test_card_link_deleted_with_card(client: TestClient, monkeypatch) -> None:
    graph_id, a, _ = _setup(client)
    study_id, card_id = _make_study_and_card(client, monkeypatch, graph_id)
    client.post(f"/api/v1/problem-cards/{card_id}/links", json={"shared_problem_id": a})

    assert client.delete(f"/api/v1/paper-problem-cards/{card_id}").status_code == 204
    assert client.get(f"/api/v1/graphs/{graph_id}/card-links").json() == []

    study2_id, card_id2 = _make_study_and_card(client, monkeypatch, graph_id)
    client.post(f"/api/v1/problem-cards/{card_id2}/links", json={"shared_problem_id": a})
    assert client.delete(f"/api/v1/paper-studies/{study2_id}").status_code == 204
    assert client.get(f"/api/v1/graphs/{graph_id}/card-links").json() == []


def test_coverage_counts_dedupe_by_study(client: TestClient, monkeypatch) -> None:
    graph_id, a, _ = _setup(client)
    _, core_card = _make_study_and_card(client, monkeypatch, graph_id, selected=True)
    client.post(f"/api/v1/problem-cards/{core_card}/links", json={"shared_problem_id": a})

    study2, touched_card = _make_study_and_card(client, monkeypatch, graph_id)
    client.post(
        f"/api/v1/problem-cards/{touched_card}/links",
        json={"shared_problem_id": a, "link_type": "TOUCHED"},
    )
    # 同一篇论文的第二张卡也指向同一问题：paper 数不应增加
    extra_card = client.post(
        f"/api/v1/paper-studies/{study2}/problem-cards",
        json={"title": "同论文第二卡"},
    ).json()
    client.post(
        f"/api/v1/problem-cards/{extra_card['id']}/links",
        json={"shared_problem_id": a, "link_type": "TOUCHED"},
    )

    detail = client.get(f"/api/v1/problems/{a}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["coverage_paper_count"] == 2
    assert body["coverage_core_count"] == 1
    assert body["coverage_touched_count"] == 1


def test_positions_upsert_and_bundle(client: TestClient, monkeypatch) -> None:
    graph_id, a, _ = _setup(client)
    study_id, card_id = _make_study_and_card(client, monkeypatch, graph_id)

    saved = client.put(
        f"/api/v1/graphs/{graph_id}/problem-map/positions",
        json=[
            {"entity_type": "PROBLEM", "entity_id": a, "position_x": 100, "position_y": 200},
            {"entity_type": "PAPER", "entity_id": study_id, "position_x": 10, "position_y": 20},
            {"entity_type": "CARD", "entity_id": card_id, "position_x": 50, "position_y": 120},
        ],
    )
    assert saved.status_code == 200
    assert len(saved.json()) == 3

    updated = client.put(
        f"/api/v1/graphs/{graph_id}/problem-map/positions",
        json=[{"entity_type": "PROBLEM", "entity_id": a, "position_x": 999, "position_y": 888}],
    )
    assert updated.status_code == 200
    assert len(updated.json()) == 1
    assert updated.json()[0]["position_x"] == 999

    bundle = client.get(f"/api/v1/graphs/{graph_id}/problem-map")
    assert bundle.status_code == 200
    body = bundle.json()
    assert len(body["problems"]) == 2
    assert len(body["edges"]) == 0
    assert len(body["papers"]) == 1
    assert body["papers"][0]["study_id"] == study_id
    assert len(body["papers"][0]["cards"]) == 1
    assert body["papers"][0]["cards"][0]["qualitative_overview"] == "这是一条用于画布展示的定性概述"
    assert body["papers"][0]["research_context"] == "训练系统"
    assert body["papers"][0]["core_problem"] == "资源错配"
    assert body["papers"][0]["main_approach"] == "解耦任务"
    assert len(body["positions"]) == 3


def test_graph_delete_cleans_problem_map(client: TestClient, monkeypatch) -> None:
    graph_id, a, b = _setup(client)
    edge = client.post(
        f"/api/v1/graphs/{graph_id}/problem-edges",
        json={"source_problem_id": a, "target_problem_id": b},
    ).json()
    study_id, card_id = _make_study_and_card(client, monkeypatch, graph_id)
    client.post(f"/api/v1/problem-cards/{card_id}/links", json={"shared_problem_id": a})
    client.put(
        f"/api/v1/graphs/{graph_id}/problem-map/positions",
        json=[{"entity_type": "PROBLEM", "entity_id": a, "position_x": 1, "position_y": 2}],
    )

    assert client.delete(f"/api/v1/graphs/{graph_id}").status_code == 204
    assert client.get(f"/api/v1/graphs/{graph_id}/problem-map").status_code == 404
    assert client.get(f"/api/v1/graphs/{graph_id}/problems").status_code == 404
    assert edge  # keep reference
    assert study_id  # keep reference
