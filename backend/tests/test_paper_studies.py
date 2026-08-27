import json

from app.services.llm_gateway import StreamChunk


def _graph(client):
    return client.post("/api/v1/graphs", json={"title": "Paper graph"}).json()["id"]


def test_paper_study_title_can_be_renamed(client):
    graph_id = _graph(client)
    study = client.post(f"/api/v1/graphs/{graph_id}/paper-studies", json={"title": "未命名论文理解"}).json()

    renamed = client.patch(f"/api/v1/paper-studies/{study['id']}", json={"title": "AReaL 论文理解"})

    assert renamed.status_code == 200
    assert renamed.json()["title"] == "AReaL 论文理解"
    assert client.get(f"/api/v1/paper-studies/{study['id']}").json()["title"] == "AReaL 论文理解"


def test_paper_understanding_requires_user_confirmed_overview(client, monkeypatch):
    graph_id = _graph(client)
    study = client.post(f"/api/v1/graphs/{graph_id}/paper-studies", json={"title": "RollArt"}).json()
    assert study["overview"]["user_status"] == "DRAFT"
    monkeypatch.setattr("app.services.paper_study.documents.extract_pdf_text", lambda *_: "PRIMARY PAPER TEXT")

    uploaded = client.post(
        f"/api/v1/paper-studies/{study['id']}/document",
        files={"file": ("paper.pdf", b"dummy", "application/pdf")},
    )
    assert uploaded.status_code == 201
    preview = client.get(f"/api/v1/paper-studies/{study['id']}/document/source-text")
    assert preview.status_code == 200
    assert preview.json()["content"] == "PRIMARY PAPER TEXT"
    assert preview.json()["character_count"] == len("PRIMARY PAPER TEXT")

    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.require_provider", lambda *_: None)
    monkeypatch.setattr(
        "app.services.llm_gateway.LLMGateway.extract_kimi_file",
        lambda *_args, **_kwargs: "paper source text",
    )
    monkeypatch.setattr(
        "app.services.llm_gateway.LLMGateway.stream",
        lambda _self, **_kwargs: iter([StreamChunk(content_delta="evidence brief")]),
    )
    assert client.post(f"/api/v1/paper-studies/{study['id']}/document/analyze").status_code == 200
    assert client.post(f"/api/v1/paper-studies/{study['id']}/problem-cards", json={"title": "问题"}).status_code == 400

    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", lambda _self, **_kwargs: iter([StreamChunk(content_delta="AI 通俗介绍")]))
    started = client.post(f"/api/v1/paper-studies/{study['id']}/conversations/OVERVIEW/start")
    assert started.status_code == 200
    assert started.json()["messages"][0]["role"] == "ASSISTANT"
    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", lambda _self, **_kwargs: iter([StreamChunk(content_delta="AI 回答追问")]))
    assert client.post(f"/api/v1/paper-studies/{study['id']}/conversations/messages", json={"stage": "OVERVIEW", "content": "这里的瓶颈到底是什么？"}).status_code == 200
    incomplete = client.patch(f"/api/v1/paper-studies/{study['id']}/overview", json={"user_status": "CONFIRMED"})
    assert incomplete.status_code == 400
    assert incomplete.json()["error"]["code"] == "OVERVIEW_FIELDS_REQUIRED"

    confirmed = client.patch(
        f"/api/v1/paper-studies/{study['id']}/overview",
        json={"research_context":"训练系统", "core_problem":"资源错配", "main_approach":"解耦任务", "claimed_effect":"降低等待", "user_understanding": "这是一个暂定理解", "user_status": "CONFIRMED"},
    )
    assert confirmed.status_code == 200

    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", lambda _self, **_kwargs: iter([StreamChunk(content_delta="AI 开始讨论问题")]))
    assert client.post(f"/api/v1/paper-studies/{study['id']}/conversations/PROBLEM_MAP/start").status_code == 200
    assert client.post(f"/api/v1/paper-studies/{study['id']}/problem-cards", json={"title": "问题"}).status_code == 400
    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", lambda _self, **_kwargs: iter([StreamChunk(content_delta="AI 问题追问回答")]))
    assert client.post(f"/api/v1/paper-studies/{study['id']}/conversations/messages", json={"stage": "PROBLEM_MAP", "content": "长尾等待具体如何产生？"}).status_code == 200

    generated = client.post(f"/api/v1/paper-studies/{study['id']}/problem-cards", json={"title": "长尾等待", "qualitative_overview": "慢任务阻塞批次", "technical_interpretation": "barrier wait", "paper_claims": ["实验显示"], "paper_not_said": ["没有证明所有环境"], "verification_anchor": "§2", "verification_prompt": "解释为什么会阻塞"})
    assert generated.status_code == 201
    card = generated.json()
    assert card["title"] == "长尾等待"
    assert card["selected"] is False
    assert client.delete(f"/api/v1/paper-problem-cards/{card['id']}").status_code == 204
    assert client.get(f"/api/v1/paper-studies/{study['id']}").json()["problem_cards"] == []


def test_concept_is_only_written_to_graph_after_explicit_action(client, monkeypatch):
    graph_id = _graph(client)
    study = client.post(f"/api/v1/graphs/{graph_id}/paper-studies", json={"title": "Paper"}).json()
    monkeypatch.setattr("app.services.paper_study.documents.extract_pdf_text", lambda *_: "PRIMARY PAPER TEXT")
    document = client.post(f"/api/v1/paper-studies/{study['id']}/document", files={"file": ("paper.pdf", b"dummy", "application/pdf")})
    assert document.status_code == 201
    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.require_provider", lambda *_: None)
    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.extract_kimi_file", lambda *_args, **_kwargs: "source")
    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", lambda _self, **_kwargs: iter([StreamChunk(content_delta="brief")]))
    client.post(f"/api/v1/paper-studies/{study['id']}/document/analyze")
    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", lambda _self, **_kwargs: iter([StreamChunk(content_delta="intro")]))
    client.post(f"/api/v1/paper-studies/{study['id']}/conversations/OVERVIEW/start")
    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", lambda _self, **_kwargs: iter([StreamChunk(content_delta="answer")]))
    client.post(f"/api/v1/paper-studies/{study['id']}/conversations/messages", json={"stage":"OVERVIEW", "content":"为什么？"})
    client.patch(f"/api/v1/paper-studies/{study['id']}/overview", json={"research_context":"x", "core_problem":"x", "main_approach":"x", "claimed_effect":"x", "user_understanding": "understanding", "user_status": "CONFIRMED"})
    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", lambda _self, **_kwargs: iter([StreamChunk(content_delta="problem intro")]))
    client.post(f"/api/v1/paper-studies/{study['id']}/conversations/PROBLEM_MAP/start")
    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", lambda _self, **_kwargs: iter([StreamChunk(content_delta="problem answer")]))
    client.post(f"/api/v1/paper-studies/{study['id']}/conversations/messages", json={"stage":"PROBLEM_MAP", "content":"有哪些问题？"})
    card = client.post(f"/api/v1/paper-studies/{study['id']}/problem-cards", json={"title":"问题", "qualitative_overview":"x", "technical_interpretation":"y", "paper_claims":[], "paper_not_said":[], "verification_anchor":"§1", "verification_prompt":"解释"}).json()
    landscape = {"items":[
        {"key":"env","title":"容器初始化","type":"MECHANISM","qualitative_overview":"启动环境","technical_interpretation":"容器生命周期初始化","causal_role":"产生环境启动延迟","paper_anchor":"§2"},
        {"key":"tail","title":"长尾延迟","type":"PHENOMENON","qualitative_overview":"慢任务拖慢批次","technical_interpretation":"同步屏障等待","causal_role":"放大批次完成时间","paper_anchor":"§3"},
    ]}
    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", lambda _self, **_kwargs: iter([StreamChunk(content_delta=json.dumps(landscape, ensure_ascii=False))]))
    mapped = client.post(f"/api/v1/paper-problem-cards/{card['id']}/concept-map/generate")
    assert mapped.status_code == 200
    assert mapped.json()["workflow_stage"] == "LANDSCAPE"
    assert mapped.json()["landscape_items"][0]["key"] == "env"
    # The review call is deliberately mocked separately so the test verifies that
    # each human-confirmed stage triggers its own model request.
    review = {"items":[{"key":"env","title":"容器初始化","type":"MECHANISM","graph_candidate":True,"reason":"需要理解环境生命周期","reusable_beyond_paper":"可迁移到容器化系统","causal_explanation_need":"解释启动延迟如何产生"}]}
    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", lambda _self, **_kwargs: iter([StreamChunk(content_delta=json.dumps(review, ensure_ascii=False))]))
    reviewed = client.post(f"/api/v1/paper-problem-cards/{card['id']}/concept-map/review")
    assert reviewed.status_code == 200
    assert reviewed.json()["workflow_stage"] == "REVIEW"
    assert reviewed.json()["candidate_review"][0]["key"] == "env"
    assert len(reviewed.json()["candidate_review"]) == 2
    assert reviewed.json()["candidate_review"][1]["key"] == "tail"
    assert reviewed.json()["candidate_review"][1]["graph_candidate"] is False
    assert reviewed.json()["candidate_review"][1]["eligible"] is False
    concept = {"items":[{"key":"env","title":"容器初始化","explanation":"启动环境","category":"MUST","paper_anchor":"§2"}],"relations":[]}
    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", lambda _self, **_kwargs: iter([StreamChunk(content_delta=json.dumps(concept, ensure_ascii=False))]))
    mapped = client.post(f"/api/v1/paper-problem-cards/{card['id']}/concept-map/finalize", json={"confirmed_candidate_keys":["env"]})
    assert mapped.status_code == 200
    assert mapped.json()["workflow_stage"] == "COMPLETED"
    assert client.get(f"/api/v1/graphs/{graph_id}/nodes").json() == []
    item = mapped.json()["items"][0]
    attached = client.post(f"/api/v1/paper-concept-items/{item['id']}/attach-node", json={"create_node": True})
    assert attached.status_code == 200
    created_nodes = client.get(f"/api/v1/graphs/{graph_id}/nodes").json()
    assert len(created_nodes) == 1
    assert (created_nodes[0]["position_x"], created_nodes[0]["position_y"]) == (120, 120)
    assert created_nodes[0]["understanding_level"] == "NEEDS_WORK"
    assert len(created_nodes[0]["paper_references"]) == 1
    assert created_nodes[0]["paper_references"][0]["filename"] == "paper.pdf"

    second_study = client.post(f"/api/v1/graphs/{graph_id}/paper-studies", json={"title": "Second paper"}).json()
    second_document = client.post(
        f"/api/v1/paper-studies/{second_study['id']}/document",
        files={"file": ("second.pdf", b"dummy", "application/pdf")},
    )
    assert second_document.status_code == 201
    linked = client.post(
        f"/api/v1/nodes/{created_nodes[0]['id']}/paper-references",
        json={"document_id": second_document.json()["id"], "link_type": "PROBLEM_EVIDENCE"},
    )
    assert linked.status_code == 200
    assert {reference["filename"] for reference in linked.json()["paper_references"]} == {"paper.pdf", "second.pdf"}


def test_paper_conversation_streams_and_persists(client, monkeypatch):
    graph_id = _graph(client)
    study = client.post(f"/api/v1/graphs/{graph_id}/paper-studies", json={"title": "Streaming paper"}).json()
    monkeypatch.setattr("app.services.paper_study.documents.extract_pdf_text", lambda *_: "PRIMARY PAPER TEXT")
    uploaded = client.post(f"/api/v1/paper-studies/{study['id']}/document", files={"file": ("paper.pdf", b"dummy", "application/pdf")})
    assert uploaded.status_code == 201
    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.require_provider", lambda *_: None)
    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", lambda _self, **_kwargs: iter([StreamChunk(content_delta="第一段"), StreamChunk(content_delta="第二段")]))
    with client.stream("POST", f"/api/v1/paper-studies/{study['id']}/conversations/OVERVIEW/start/stream") as response:
        body = "".join(response.iter_text())
    assert response.status_code == 200
    assert 'event: delta' in body and '第一段' in body and 'event: completed' in body
    stored = client.get(f"/api/v1/paper-studies/{study['id']}").json()
    assert stored["messages"][-1]["content"] == "第一段第二段"

    monkeypatch.setattr("app.services.llm_gateway.LLMGateway.stream", lambda _self, **_kwargs: iter([StreamChunk(content_delta="追问回答")]))
    with client.stream("POST", f"/api/v1/paper-studies/{study['id']}/conversations/messages/stream", json={"stage": "OVERVIEW", "content": "为什么？"}) as response:
        body = "".join(response.iter_text())
    assert response.status_code == 200
    assert 'event: completed' in body
    stored = client.get(f"/api/v1/paper-studies/{study['id']}").json()
    assert [message["content"] for message in stored["messages"][-2:]] == ["为什么？", "追问回答"]


def test_temporary_knowledge_inquiry_is_isolated_and_can_create_node(client, monkeypatch):
    graph_id = _graph(client)
    study = client.post(f"/api/v1/graphs/{graph_id}/paper-studies", json={"title": "Temporary inquiry"}).json()
    monkeypatch.setattr("app.services.paper_study.documents.extract_pdf_text", lambda *_: "PRIMARY PAPER TEXT")
    uploaded = client.post(
        f"/api/v1/paper-studies/{study['id']}/document",
        files={"file": ("paper.pdf", b"dummy", "application/pdf")},
    )
    assert uploaded.status_code == 201

    inquiry = client.post(
        f"/api/v1/paper-studies/{study['id']}/knowledge-inquiries",
        json={"title": "注意力机制"},
    )
    assert inquiry.status_code == 201
    inquiry_id = inquiry.json()["id"]
    assert client.get(f"/api/v1/paper-studies/{study['id']}").json()["messages"] == []

    monkeypatch.setattr(
        "app.services.llm_gateway.LLMGateway.stream",
        lambda _self, **_kwargs: iter([StreamChunk(content_delta="它用于按相关性聚合信息。")]),
    )
    with client.stream(
        "POST",
        f"/api/v1/paper-studies/{study['id']}/knowledge-inquiries/{inquiry_id}/messages/stream",
        json={"content": "它在这篇论文里具体做什么？"},
    ) as response:
        body = "".join(response.iter_text())
    assert response.status_code == 200
    assert "event: completed" in body

    inquiry_after = client.get(
        f"/api/v1/paper-studies/{study['id']}/knowledge-inquiries/{inquiry_id}",
    ).json()
    assert [message["role"] for message in inquiry_after["messages"]] == ["USER", "ASSISTANT"]
    assert client.get(f"/api/v1/paper-studies/{study['id']}").json()["messages"] == []

    saved = client.post(
        f"/api/v1/paper-studies/{study['id']}/knowledge-inquiries/{inquiry_id}/save-card",
        json={"title": "注意力机制", "summary": "根据论文证据，按相关性聚合信息。"},
    )
    assert saved.status_code == 200
    node = saved.json()["node"]
    assert node["title"] == "注意力机制"
    assert node["node_type"] == "CONCEPT"
    assert node["summary_preview"] == "根据论文证据，按相关性聚合信息。"
    assert node["paper_references"][0]["filename"] == "paper.pdf"
    assert saved.json()["inquiry"]["status"] == "SAVED"
    assert client.get(f"/api/v1/graphs/{graph_id}/nodes").json()[0]["id"] == node["id"]
