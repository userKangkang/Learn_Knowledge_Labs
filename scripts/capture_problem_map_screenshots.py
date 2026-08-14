"""
Seed a disposable demo paper-problem map (does not modify other graphs) and capture
paper-problem-map screenshots.

Prereqs: backend :8000 and frontend :5173 running.
Usage (from repo root):
  uv run --with playwright --with httpx --project backend python scripts/capture_problem_map_screenshots.py
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

OUT_DIR = ROOT / "docs" / "images" / "usage"
API = "http://127.0.0.1:8000/api/v1"
WEB = "http://127.0.0.1:5173"
DEMO_TITLE = "[文档演示] 论文-问题导图示例图"


def api_json(client: httpx.Client, method: str, path: str, **kwargs):
    response = client.request(method, f"{API}{path}", **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text}")
    if response.status_code == 204 or not response.content:
        return None
    return response.json()


def seed_demo(client: httpx.Client) -> dict:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.config import get_settings
    from app.models.paper_study import PaperProblemCard, PaperStudyMessage, PaperStudyOverview

    graphs = api_json(client, "GET", "/graphs") or []
    for graph in graphs:
        if graph.get("title") == DEMO_TITLE:
            api_json(client, "DELETE", f"/graphs/{graph['id']}")

    graph = api_json(
        client,
        "POST",
        "/graphs",
        json={"title": DEMO_TITLE, "description": "论文-问题导图静态截图专用，可删"},
    )
    gid = graph["id"]

    papers = [
        {
            "title": "RollArt：长尾环境下的分布式训练",
            "cards": [
                ("慢任务阻塞批次完成", True, "等待最慢任务导致整批训练被拖住", "同步屏障等待时间由最慢 worker 决定"),
                ("长尾回合时长拖慢采样", False, "少数超长回合显著拉长单轮采样时间", "回合长度分布右尾主导平均时长"),
            ],
        },
        {
            "title": "稀疏奖励下的策略梯度稳定训练",
            "cards": [
                ("稀疏奖励下策略梯度方差大", True, "奖励信号稀疏时梯度估计方差过大", "优势估计需要更稳的基线"),
                ("长尾任务分布影响样本效率", False, "任务长度差异导致采样效率不均", "样本量分配与回合长度耦合"),
            ],
        },
        {
            "title": "离线强化学习中的分布偏移",
            "cards": [
                ("行为策略与目标策略分布偏移", True, "离线数据来自旧策略，评估新策略时分布不匹配", "需要保守估计或约束策略差异"),
            ],
        },
    ]

    study_ids: dict[str, str] = {}
    card_ids: dict[str, str] = {}
    for paper in papers:
        study = api_json(client, "POST", f"/graphs/{gid}/paper-studies", json={"title": paper["title"]})
        study_ids[paper["title"]] = study["id"]

    engine = create_engine(get_settings().database_url, connect_args={"check_same_thread": False})
    db = sessionmaker(bind=engine, autoflush=False)()
    try:
        for paper in papers:
            study_id = study_ids[paper["title"]]
            overview = db.get(PaperStudyOverview, study_id)
            if not overview:
                raise RuntimeError(f"missing overview for study {study_id}")
            overview.research_context = "分布式训练与强化学习采样的资源效率问题"
            overview.core_problem = "训练吞吐与稳定性受长尾/稀疏信号制约"
            overview.main_approach = "解耦等待、引入基线或保守约束"
            overview.claimed_effect = "在典型基准上提升吞吐与收敛稳定性"
            overview.user_understanding = "这些论文都在处理同一类训练不稳定问题"
            overview.user_status = "CONFIRMED"
            db.add(
                PaperStudyMessage(
                    id=str(uuid.uuid4()),
                    study_id=study_id,
                    stage="PROBLEM_MAP",
                    role="USER",
                    content="论文主要解决哪些问题？",
                    sequence_index=1,
                )
            )
            db.add(
                PaperStudyMessage(
                    id=str(uuid.uuid4()),
                    study_id=study_id,
                    stage="PROBLEM_MAP",
                    role="ASSISTANT",
                    content="先厘清现象与成因：哪些等待被放大了，哪些信号让梯度不稳。",
                    sequence_index=2,
                )
            )
            for index, (title, selected, qualitative, technical) in enumerate(paper["cards"]):
                card = PaperProblemCard(
                    id=str(uuid.uuid4()),
                    study_id=study_id,
                    title=title,
                    qualitative_overview=qualitative,
                    technical_interpretation=technical,
                    selected=selected,
                    status="EXPLORING" if selected else "UNOPENED",
                    order_index=index,
                )
                db.add(card)
                card_ids[(paper["title"], title)] = card.id
        db.commit()
    finally:
        db.close()

    problems = {
        "root": api_json(
            client,
            "POST",
            f"/graphs/{gid}/problems",
            json={"title": "强化学习训练效率与稳定性", "description": "多篇论文共同关注：训练能不能又快又稳地收敛"},
        ),
        "tail": api_json(
            client,
            "POST",
            f"/graphs/{gid}/problems",
            json={"title": "长尾任务拖慢同步训练", "description": "最慢任务/回合成为训练吞吐的瓶颈"},
        ),
        "sparse": api_json(
            client,
            "POST",
            f"/graphs/{gid}/problems",
            json={"title": "稀疏奖励下策略梯度方差控制", "description": "奖励稀疏导致梯度估计方差大，需要基线或保守约束"},
        ),
        "offline": api_json(
            client,
            "POST",
            f"/graphs/{gid}/problems",
            json={"title": "离线数据分布偏移", "description": "离线数据与在线评估分布不一致，直接优化会失稳"},
        ),
    }

    api_json(
        client,
        "POST",
        f"/graphs/{gid}/problem-edges",
        json={"source_problem_id": problems["root"]["id"], "target_problem_id": problems["tail"]["id"], "relation_label": "在分布式场景下"},
    )
    api_json(
        client,
        "POST",
        f"/graphs/{gid}/problem-edges",
        json={"source_problem_id": problems["root"]["id"], "target_problem_id": problems["sparse"]["id"], "relation_label": "在稀疏奖励场景下"},
    )
    api_json(
        client,
        "POST",
        f"/graphs/{gid}/problem-edges",
        json={"source_problem_id": problems["root"]["id"], "target_problem_id": problems["offline"]["id"], "relation_label": "在离线场景下"},
    )

    links = [
        ("RollArt：长尾环境下的分布式训练", "慢任务阻塞批次完成", problems["tail"]["id"], "CORE"),
        ("RollArt：长尾环境下的分布式训练", "长尾回合时长拖慢采样", problems["tail"]["id"], "TOUCHED"),
        ("稀疏奖励下的策略梯度稳定训练", "稀疏奖励下策略梯度方差大", problems["sparse"]["id"], "CORE"),
        ("稀疏奖励下的策略梯度稳定训练", "长尾任务分布影响样本效率", problems["tail"]["id"], "TOUCHED"),
        ("离线强化学习中的分布偏移", "行为策略与目标策略分布偏移", problems["offline"]["id"], "CORE"),
    ]
    for study_title, card_title, problem_id, link_type in links:
        api_json(
            client,
            "POST",
            f"/problem-cards/{card_ids[(study_title, card_title)]}/links",
            json={"shared_problem_id": problem_id, "link_type": link_type},
        )

    positions = [
        ("PAPER", study_ids["RollArt：长尾环境下的分布式训练"], 60, 50),
        ("PAPER", study_ids["稀疏奖励下的策略梯度稳定训练"], 430, 50),
        ("PAPER", study_ids["离线强化学习中的分布偏移"], 800, 50),
        ("PROBLEM", problems["tail"]["id"], 140, 300),
        ("PROBLEM", problems["sparse"]["id"], 560, 300),
        ("PROBLEM", problems["offline"]["id"], 980, 300),
        ("PROBLEM", problems["root"]["id"], 560, 560),
    ]
    api_json(
        client,
        "PUT",
        f"/graphs/{gid}/problem-map/positions",
        json=[
            {"entity_type": entity_type, "entity_id": entity_id, "position_x": x, "position_y": y}
            for entity_type, entity_id, x, y in positions
        ],
    )

    bundle = api_json(client, "GET", f"/graphs/{gid}/problem-map")
    if len(bundle["problems"]) != 4 or len(bundle["links"]) != 5:
        raise RuntimeError(f"demo seed mismatch: {json.dumps(bundle, ensure_ascii=False)}")

    return {
        "graph_id": gid,
        "study_ids": study_ids,
        "problem_ids": {key: value["id"] for key, value in problems.items()},
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

        # 1) Problem-map canvas
        page.goto(f"{WEB}/graphs/{demo['graph_id']}/problem-map", wait_until="networkidle")
        page.locator(".pm-node--problem").first.wait_for()
        time.sleep(1.2)
        shot(page, "08-problem-map-canvas.png")

        # 2) Selected shared problem -> inspector with coverage
        page.locator(".pm-node--problem").filter(has_text="长尾任务拖慢同步训练").first.click()
        page.get_by_role("heading", name="共享问题").wait_for()
        time.sleep(0.5)
        shot(page, "09-problem-map-problem-inspector.png")

        # 3) Selected paper -> cards and links
        page.locator(".pm-node--paper").filter(has_text="RollArt").first.click()
        page.get_by_role("heading", name="RollArt：长尾环境下的分布式训练").wait_for()
        time.sleep(0.5)
        shot(page, "10-problem-map-paper-inspector.png")

        browser.close()

    manifest_path = OUT_DIR / "manifest.json"
    manifest: dict = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({"problem_map_demo": demo, "generated": True})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
