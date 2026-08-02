from unittest.mock import patch

from fastapi.testclient import TestClient

from app.services.llm_gateway import StreamChunk


def _session_with_assistant(client: TestClient, monkeypatch) -> tuple[str, str, str]:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    graph = client.post("/api/v1/graphs", json={"title": "G"}).json()
    node = client.post(f"/api/v1/graphs/{graph['id']}/nodes", json={"title": "N"}).json()
    session = client.post(f"/api/v1/nodes/{node['id']}/sessions", json={}).json()
    session_id = session["id"]

    def fake_stream(*_args, **kwargs):
        yield StreamChunk(content_delta="主线助手长文里有个细节。", output_tokens=4)

    with patch("app.services.chat_stream_service.LLMGateway.stream", side_effect=fake_stream):
        with client.stream(
            "POST",
            f"/api/v1/sessions/{session_id}/messages/stream",
            json={"content": "请解释一下"},
        ) as response:
            assert response.status_code == 200
            assert "event: completed" in "".join(response.iter_text())

    messages = client.get(f"/api/v1/sessions/{session_id}/messages").json()
    assert len(messages) == 2
    assert messages[1]["role"] == "ASSISTANT"
    get_settings.cache_clear()
    return session_id, messages[0]["id"], messages[1]["id"]


def test_ephemeral_temp_chat_and_save_branch(client: TestClient, monkeypatch):
    session_id, _user_id, assistant_id = _session_with_assistant(client, monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    def side_stream(*_args, **kwargs):
        yield StreamChunk(content_delta="旁支澄清回答", output_tokens=2)

    with patch("app.services.temp_chat_service.LLMGateway.stream", side_effect=side_stream):
        with client.stream(
            "POST",
            f"/api/v1/sessions/{session_id}/temp-chats/ephemeral/stream",
            json={
                "anchor_message_id": assistant_id,
                "content": "这句话具体指什么？",
                "prior_turns": [],
            },
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())
            assert "event: completed" in body
            assert '"ephemeral": true' in body

    # Ephemeral must not pollute mainline messages.
    mainline = client.get(f"/api/v1/sessions/{session_id}/messages").json()
    assert len(mainline) == 2
    assert all(m.get("branch_id") in (None, "") for m in mainline)

    saved = client.post(
        f"/api/v1/sessions/{session_id}/branches",
        json={
            "anchor_message_id": assistant_id,
            "title": "澄清细节",
            "turns": [
                {"role": "USER", "content": "这句话具体指什么？"},
                {"role": "ASSISTANT", "content": "旁支澄清回答"},
            ],
        },
    )
    assert saved.status_code == 201, saved.text
    branch = saved.json()
    assert branch["anchor_message_id"] == assistant_id
    assert branch["message_count"] == 2
    assert len(branch["messages"]) == 2
    assert all(m["branch_id"] == branch["id"] for m in branch["messages"])

    mainline_after = client.get(f"/api/v1/sessions/{session_id}/messages").json()
    assert len(mainline_after) == 2
    assert {m["id"] for m in mainline_after} == {m["id"] for m in mainline}

    listed = client.get(
        f"/api/v1/sessions/{session_id}/branches",
        params={"anchor_message_id": assistant_id},
    ).json()
    assert len(listed) == 1
    assert listed[0]["id"] == branch["id"]
    get_settings.cache_clear()


def test_branch_continue_stays_off_mainline(client: TestClient, monkeypatch):
    session_id, _user_id, assistant_id = _session_with_assistant(client, monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    branch = client.post(
        f"/api/v1/sessions/{session_id}/branches",
        json={
            "anchor_message_id": assistant_id,
            "turns": [
                {"role": "USER", "content": "先问一句"},
                {"role": "ASSISTANT", "content": "先答一句"},
            ],
        },
    ).json()

    def cont_stream(*_args, **kwargs):
        yield StreamChunk(content_delta="旁支续聊", output_tokens=2)

    with patch("app.services.temp_chat_service.LLMGateway.stream", side_effect=cont_stream):
        with client.stream(
            "POST",
            f"/api/v1/branches/{branch['id']}/messages/stream",
            json={"content": "再问一句"},
        ) as response:
            assert response.status_code == 200
            assert "event: completed" in "".join(response.iter_text())

    mainline = client.get(f"/api/v1/sessions/{session_id}/messages").json()
    assert len(mainline) == 2

    detail = client.get(f"/api/v1/branches/{branch['id']}").json()
    assert detail["message_count"] == 4
    assert detail["messages"][-1]["content"] == "旁支续聊"
    assert detail["messages"][-1]["branch_id"] == branch["id"]
    get_settings.cache_clear()
