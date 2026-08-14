from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.services.llm_gateway import LLMGateway, StreamChunk


def _graph_node_session(client: TestClient) -> tuple[str, str, str]:
    graph = client.post("/api/v1/graphs", json={"title": "G"}).json()
    node = client.post(f"/api/v1/graphs/{graph['id']}/nodes", json={"title": "N1"}).json()
    session = client.post(f"/api/v1/nodes/{node['id']}/sessions", json={}).json()
    return graph["id"], node["id"], session["id"]


def _pdf_with_text(text: str) -> bytes:
    # Minimal PDF with a text drawing operator.
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET"
    objects = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    stream = content.encode("latin-1")
    objects.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("latin-1") + stream + b"\nendstream\nendobj\n"
    )
    objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin-1")
    )
    return bytes(out)


def test_llm_settings(client: TestClient):
    data = client.get("/api/v1/llm/settings").json()
    assert data["model"] == "deepseek-v4-flash"
    assert data["search_model"] == "deepseek-v4-flash"
    assert data["kimi_model"] == "kimi-k3"
    assert data["web_search_uses_flash"] is True
    assert data["supports_pdf_text_extract"] is True
    assert data["supports_image_vision"] is True
    assert data["multimodal_provider"] == "kimi"


def test_upload_accepts_image(client: TestClient, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.config import get_settings

    get_settings.cache_clear()
    _, _, session_id = _graph_node_session(client)
    response = client.post(
        f"/api/v1/sessions/{session_id}/attachments",
        files={"file": ("photo.png", b"\x89PNG\r\n\x1a\nfakepng", "image/png")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["kind"] == "image"
    get_settings.cache_clear()


def test_upload_pdf_and_stream(client: TestClient, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()

    _, _, session_id = _graph_node_session(client)
    pdf = _pdf_with_text("Paper abstract about graphs")
    upload = client.post(
        f"/api/v1/sessions/{session_id}/attachments",
        files={"file": ("paper.pdf", pdf, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    attachment = upload.json()
    assert attachment["extract_status"] in {"SUCCEEDED", "FAILED"}

    def fake_stream(*_args, **kwargs):
        # With attachments, route must force Kimi file digest mode.
        assert kwargs.get("provider") == "kimi"
        assert kwargs.get("model") == "kimi-k3"
        assert kwargs.get("web_search") is False
        yield StreamChunk(content_delta="你好，")
        yield StreamChunk(content_delta="这是回复。", output_tokens=4)

    monkeypatch.setenv("MOONSHOT_API_KEY", "kimi-test-key")
    get_settings.cache_clear()

    with patch("app.services.chat_stream_service.LLMGateway.stream", side_effect=fake_stream):
        with client.stream(
            "POST",
            f"/api/v1/sessions/{session_id}/messages/stream",
            json={"content": "请总结附件", "attachment_ids": [attachment["id"]], "web_search": False},
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())
            assert "event: request_created" in body
            assert '"web_search": false' in body
            assert "event: context_built" in body
            assert "event: delta" in body
            assert "event: completed" in body

    messages = client.get(f"/api/v1/sessions/{session_id}/messages").json()
    assert len(messages) == 2
    assert messages[0]["role"] == "USER"
    assert messages[0]["attachments"]
    assert messages[1]["role"] == "ASSISTANT"
    assert messages[1]["content"] == "你好，这是回复。"
    assert messages[1]["status"] == "ACTIVE"

    get_settings.cache_clear()


def test_stream_web_search_uses_flash(client: TestClient, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    _, _, session_id = _graph_node_session(client)

    def fake_stream(*_args, **kwargs):
        assert kwargs.get("provider") == "deepseek"
        assert kwargs.get("web_search") is True
        assert kwargs.get("model") == "deepseek-v4-flash"
        yield StreamChunk(status_text="正在联网搜索…")
        yield StreamChunk(content_delta="联网后的答案", output_tokens=3)

    with patch("app.services.chat_stream_service.LLMGateway.stream", side_effect=fake_stream):
        with client.stream(
            "POST",
            f"/api/v1/sessions/{session_id}/messages/stream",
            json={"content": "最近有哪些顶会论文？", "web_search": True},
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())
            assert '"web_search": true' in body
            assert "event: status" in body
            assert "event: completed" in body

    messages = client.get(f"/api/v1/sessions/{session_id}/messages").json()
    assert messages[-1]["content"] == "联网后的答案"
    get_settings.cache_clear()


def test_stream_web_search_can_route_to_kimi(client: TestClient, monkeypatch):
    monkeypatch.setenv("MOONSHOT_API_KEY", "kimi-test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    _, _, session_id = _graph_node_session(client)

    def fake_stream(*_args, **kwargs):
        assert kwargs.get("provider") == "kimi"
        assert kwargs.get("web_search") is True
        assert kwargs.get("model") == "kimi-k3"
        yield StreamChunk(content_delta="Kimi 联网答案")

    with patch("app.services.chat_stream_service.LLMGateway.stream", side_effect=fake_stream):
        with client.stream(
            "POST",
            f"/api/v1/sessions/{session_id}/messages/stream",
            json={"content": "最近有哪些顶会论文？", "web_search": True, "text_model": "kimi-k3"},
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())
            assert '"provider": "kimi"' in body
            assert '"web_search": true' in body
            assert "Kimi 联网答案" in body
    get_settings.cache_clear()


def test_kimi_gateway_executes_official_formula_search(monkeypatch):
    settings = SimpleNamespace(
        moonshot_api_key="kimi-test-key",
        moonshot_base_url="https://api.moonshot.cn/v1",
        llm_reasoning_effort="high",
    )
    gateway = LLMGateway(settings)  # type: ignore[arg-type]
    calls: list[tuple[str, str, dict | None]] = []

    class FakeResponse:
        def __init__(self, payload: dict):
            self.status_code = 200
            self._payload = payload
            self.text = ""

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, url, *, headers):
            calls.append(("GET", url, None))
            return FakeResponse({"tools": [{"type": "function", "function": {"name": "web_search"}}]})

        def post(self, url, *, headers, json):
            calls.append(("POST", url, json))
            if url.endswith("/chat/completions"):
                return FakeResponse(
                    {
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": None,
                                    "reasoning_content": "需要搜索",
                                    "tool_calls": [
                                        {
                                            "id": "web_search:0",
                                            "type": "function",
                                            "function": {"name": "web_search", "arguments": '{"query":"相关论文"}'},
                                        }
                                    ],
                                },
                                "finish_reason": "tool_calls",
                            }
                        ]
                    }
                )
            return FakeResponse({"context": {"encrypted_output": "encrypted-search-result"}})

    final_request: dict = {}

    def fake_final_stream(url, body, *, headers, retry_attempt=0):
        final_request.update({"url": url, "body": body, "headers": headers})
        yield StreamChunk(content_delta="最终联网回答")

    monkeypatch.setattr("app.services.llm_gateway.httpx.Client", FakeClient)
    monkeypatch.setattr(gateway, "_iter_chat_sse", fake_final_stream)
    chunks = list(
        gateway.stream(
            provider="kimi",
            model="kimi-k3",
            system_prompt="system",
            messages=[{"role": "user", "content": "搜索相关论文"}],
            web_search=True,
        )
    )

    assert any(chunk.status_text == "Kimi 正在执行联网搜索…" for chunk in chunks)
    assert chunks[-1].content_delta == "最终联网回答"
    assert calls[0][0] == "GET" and calls[0][1].endswith("/formulas/moonshot/web-search:latest/tools")
    planning = next(body for method, url, body in calls if method == "POST" and url.endswith("/chat/completions"))
    assert planning["tool_choice"] == "required"
    fiber = next(body for method, url, body in calls if method == "POST" and url.endswith("/fibers"))
    assert fiber == {"name": "web_search", "arguments": '{"query":"相关论文"}'}
    assert final_request["body"]["tool_choice"] == "none"
    assert final_request["body"]["stream"] is True
    assert final_request["body"]["messages"][-1] == {
        "role": "tool",
        "tool_call_id": "web_search:0",
        "content": "encrypted-search-result",
    }


def test_text_model_kimi_without_files(client: TestClient, monkeypatch):
    monkeypatch.setenv("MOONSHOT_API_KEY", "kimi-test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    _, _, session_id = _graph_node_session(client)

    def fake_stream(*_args, **kwargs):
        assert kwargs.get("provider") == "kimi"
        assert kwargs.get("model") == "kimi-k3"
        yield StreamChunk(content_delta="kimi reply", output_tokens=2)

    with patch("app.services.chat_stream_service.LLMGateway.stream", side_effect=fake_stream):
        with client.stream(
            "POST",
            f"/api/v1/sessions/{session_id}/messages/stream",
            json={"content": "解释一下强化学习", "text_model": "kimi-k3"},
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())
            assert "event: completed" in body
    get_settings.cache_clear()


def test_stream_requires_api_key(client: TestClient, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()
    _, _, session_id = _graph_node_session(client)
    response = client.post(
        f"/api/v1/sessions/{session_id}/messages/stream",
        json={"content": "hello"},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LLM_NOT_CONFIGURED"
    get_settings.cache_clear()


def test_retry_last_user_message_only(client: TestClient, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    _, _, session_id = _graph_node_session(client)

    empty = client.post(f"/api/v1/sessions/{session_id}/messages/retry/stream", json={})
    assert empty.status_code == 400
    assert empty.json()["error"]["code"] == "NOTHING_TO_RETRY"

    def first_stream(*_args, **kwargs):
        yield StreamChunk(content_delta="第一次回答", output_tokens=2)

    with patch("app.services.chat_stream_service.LLMGateway.stream", side_effect=first_stream):
        with client.stream(
            "POST",
            f"/api/v1/sessions/{session_id}/messages/stream",
            json={"content": "解释一下图", "text_model": "deepseek-v4-flash"},
        ) as response:
            assert response.status_code == 200
            assert "event: completed" in "".join(response.iter_text())

    before = client.get(f"/api/v1/sessions/{session_id}/messages").json()
    assert len(before) == 2
    user_id = before[0]["id"]
    old_assistant_id = before[1]["id"]
    assert before[1]["content"] == "第一次回答"

    def retry_stream(*_args, **kwargs):
        assert kwargs.get("provider") == "kimi"
        yield StreamChunk(content_delta="重试后的回答", output_tokens=3)

    monkeypatch.setenv("MOONSHOT_API_KEY", "kimi-test-key")
    get_settings.cache_clear()

    with patch("app.services.chat_stream_service.LLMGateway.stream", side_effect=retry_stream):
        with client.stream(
            "POST",
            f"/api/v1/sessions/{session_id}/messages/retry/stream",
            json={"text_model": "kimi-k3"},
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())
            assert "event: completed" in body
            assert f'"user_message_id": "{user_id}"' in body

    after = client.get(f"/api/v1/sessions/{session_id}/messages").json()
    assert len(after) == 2
    assert after[0]["id"] == user_id
    assert after[0]["content"] == "解释一下图"
    assert after[1]["id"] != old_assistant_id
    assert after[1]["content"] == "重试后的回答"
    assert after[1]["status"] == "ACTIVE"
    get_settings.cache_clear()


def test_retry_keeps_attachments_on_last_user(client: TestClient, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("MOONSHOT_API_KEY", "kimi-test-key")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.config import get_settings

    get_settings.cache_clear()
    _, _, session_id = _graph_node_session(client)

    pdf = _pdf_with_text("Attachment body for retry")
    upload = client.post(
        f"/api/v1/sessions/{session_id}/attachments",
        files={"file": ("note.pdf", pdf, "application/pdf")},
    )
    assert upload.status_code == 201
    attachment_id = upload.json()["id"]

    def fail_once(*_args, **kwargs):
        raise RuntimeError("provider down")

    with patch("app.services.chat_stream_service.LLMGateway.stream", side_effect=fail_once):
        with client.stream(
            "POST",
            f"/api/v1/sessions/{session_id}/messages/stream",
            json={"content": "解析", "attachment_ids": [attachment_id]},
        ) as response:
            assert response.status_code == 200
            assert "event: failed" in "".join(response.iter_text())

    failed = client.get(f"/api/v1/sessions/{session_id}/messages").json()
    assert failed[0]["attachments"]
    assert failed[1]["status"] == "FAILED"
    user_id = failed[0]["id"]

    def ok_stream(*_args, **kwargs):
        assert kwargs.get("provider") == "kimi"
        yield StreamChunk(content_delta="附件摘要成功", output_tokens=2)

    with patch("app.services.chat_stream_service.LLMGateway.stream", side_effect=ok_stream):
        with client.stream(
            "POST",
            f"/api/v1/sessions/{session_id}/messages/retry/stream",
            json={},
        ) as response:
            assert response.status_code == 200
            assert "event: completed" in "".join(response.iter_text())

    messages = client.get(f"/api/v1/sessions/{session_id}/messages").json()
    assert len(messages) == 2
    assert messages[0]["id"] == user_id
    assert messages[0]["attachments"][0]["id"] == attachment_id
    assert messages[1]["content"] == "附件摘要成功"
    assert messages[1]["status"] == "ACTIVE"
    get_settings.cache_clear()
