"""
Seed a disposable demo graph (does not modify other graphs) and capture usage screenshots.

Prereqs: backend :8000 and frontend :5173 running.
Usage (from repo root):
  uv run --with playwright --with httpx --project backend python scripts/capture_usage_screenshots.py
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "images" / "usage"
API = "http://127.0.0.1:8000/api/v1"
WEB = "http://127.0.0.1:5173"
DEMO_TITLE = "[文档演示] 用法截图示例图"


def api_json(client: httpx.Client, method: str, path: str, **kwargs):
    response = client.request(method, f"{API}{path}", **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text}")
    if response.status_code == 204 or not response.content:
        return None
    return response.json()


def seed_demo(client: httpx.Client) -> dict:
    # Soft-delete any previous demo graphs with the same title so re-runs stay tidy.
    graphs = api_json(client, "GET", "/graphs") or []
    for graph in graphs:
        if graph.get("title") == DEMO_TITLE:
            api_json(client, "DELETE", f"/graphs/{graph['id']}")

    graph = api_json(client, "POST", "/graphs", json={"title": DEMO_TITLE, "description": "README 静态截图专用，可删"})
    gid = graph["id"]

    root = api_json(
        client,
        "POST",
        f"/graphs/{gid}/nodes",
        json={"title": "强化学习入门", "node_type": "TOPIC", "position_x": 120, "position_y": 180},
    )
    child_a = api_json(
        client,
        "POST",
        f"/graphs/{gid}/nodes",
        json={"title": "马尔可夫决策过程", "node_type": "CONCEPT", "position_x": 420, "position_y": 80},
    )
    child_b = api_json(
        client,
        "POST",
        f"/graphs/{gid}/nodes",
        json={"title": "策略梯度", "node_type": "METHOD", "position_x": 420, "position_y": 280},
    )

    api_json(
        client,
        "POST",
        f"/graphs/{gid}/edges",
        json={
            "source_node_id": root["id"],
            "target_node_id": child_a["id"],
            "type": "PART_OF",
        },
    )
    edge_b = api_json(
        client,
        "POST",
        f"/graphs/{gid}/edges",
        json={
            "source_node_id": root["id"],
            "target_node_id": child_b["id"],
            "type": "PREREQUISITE_OF",
        },
    )

    api_json(
        client,
        "POST",
        f"/nodes/{root['id']}/summary",
        json={
            "content": "围绕强化学习核心对象建立地图：状态、动作、奖励与策略。本摘要用于演示节点详情面板。",
            "author_type": "USER",
        },
    )

    session = api_json(client, "POST", f"/nodes/{root['id']}/sessions", json={"title": "入门问答"})
    sid = session["id"]
    user = api_json(
        client,
        "POST",
        f"/sessions/{sid}/messages",
        json={"role": "USER", "content": "策略梯度适合解决什么问题？"},
    )
    assistant = api_json(
        client,
        "POST",
        f"/sessions/{sid}/messages",
        json={
            "role": "ASSISTANT",
            "content": (
                "策略梯度直接对策略参数求梯度，适合动作空间较大或连续、难以用价值函数枚举的问题。\n\n"
                "常见要点：\n"
                "- 用回报（或优势）加权动作对数概率\n"
                "- 方差往往较大，实务上常配合基线或 Actor-Critic\n"
                "- 与值函数方法可互补，而不是互相替代"
            ),
        },
    )
    api_json(
        client,
        "POST",
        f"/sessions/{sid}/branches",
        json={
            "anchor_message_id": assistant["id"],
            "title": "什么是优势函数？",
            "turns": [
                {"role": "USER", "content": "这里的「优势」具体指什么？"},
                {
                    "role": "ASSISTANT",
                    "content": "优势函数衡量「某个动作相对平均水平好多少」，常写作 A(s,a)=Q(s,a)-V(s)。旁支仅澄清术语，不进入主线后续上下文。",
                },
            ],
        },
    )

    return {
        "graph_id": gid,
        "root_id": root["id"],
        "child_b_id": child_b["id"],
        "edge_b_id": edge_b["id"],
        "session_id": sid,
        "assistant_id": assistant["id"],
        "user_id": user["id"],
    }


def shot(page, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    page.screenshot(path=str(path), full_page=False)
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> int:
    with httpx.Client(timeout=30.0) as client:
        try:
            health = client.get(f"{API}/health")
            health.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            print(f"Backend not reachable at {API}: {exc}", file=sys.stderr)
            return 1
        demo = seed_demo(client)
        print("seeded", json.dumps(demo, ensure_ascii=False))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(20000)

        # 1) Graph list
        page.goto(WEB, wait_until="networkidle")
        page.get_by_role("heading", name="我的知识图").wait_for()
        page.get_by_text(DEMO_TITLE).wait_for()
        time.sleep(0.4)
        shot(page, "01-graph-list.png")

        # 2) Open editor canvas
        page.get_by_role("link", name=DEMO_TITLE).click()
        page.wait_for_url("**/graphs/**")
        page.get_by_role("button", name="添加节点").wait_for()
        page.locator(".k-node").filter(has_text="强化学习入门").wait_for()
        time.sleep(0.8)
        shot(page, "02-graph-editor.png")

        # 3) Select root node -> inspector
        page.locator(".k-node").filter(has_text="强化学习入门").click()
        page.get_by_role("heading", name="节点详情").wait_for()
        page.locator(".inspector").get_by_text("摘要").first.wait_for()
        time.sleep(0.4)
        shot(page, "03-node-inspector.png")

        # 4) Select edge (click edge label "前置知识")
        page.locator(".k-edge-label").filter(has_text="前置知识").first.click()
        page.get_by_role("heading", name="边详情").wait_for()
        time.sleep(0.3)
        shot(page, "04-edge-inspector.png")

        # 5) Open chat drawer from node sessions
        page.locator(".k-node").filter(has_text="强化学习入门").click()
        page.get_by_role("heading", name="节点详情").wait_for()
        page.get_by_role("button", name="打开对话").click()
        page.locator(".chat-drawer").get_by_role("button", name="临时询问").wait_for()
        time.sleep(0.5)
        shot(page, "05-chat-drawer.png")

        # 6) Temp ask panel
        page.locator(".chat-drawer").get_by_role("button", name="临时询问").click()
        page.get_by_text("主线上下文（至锚定回复）").wait_for()
        time.sleep(0.4)
        shot(page, "06-temp-ask.png")

        # Close temp ask, expand saved branch list hint
        page.locator(".temp-ask").get_by_role("button", name="关闭").click()
        expand = page.locator(".chat-drawer").get_by_role("button", name=re.compile(r"^展开旁支"))
        if expand.count():
            expand.first.click()
            time.sleep(0.3)
            shot(page, "07-branch-expand.png")

        browser.close()

    manifest = OUT_DIR / "manifest.json"
    manifest.write_text(
        json.dumps({"demo_title": DEMO_TITLE, "demo": demo, "generated": True}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"done -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
