"""Probe whether DeepSeek can enable thinking + web_search together."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def summarize(label: str, response: httpx.Response) -> None:
    print(f"=== {label} HTTP {response.status_code} ===")
    try:
        data = response.json()
    except Exception:
        print(response.text[:800])
        return
    if response.status_code >= 400:
        print(json.dumps(data, ensure_ascii=False)[:1000])
        return
    if "choices" in data:
        msg = data["choices"][0].get("message") or {}
        print("has_reasoning", bool(msg.get("reasoning_content")))
        print("reasoning_len", len(msg.get("reasoning_content") or ""))
        print("content_preview", (msg.get("content") or "")[:240].replace("\n", " "))
        print("tool_calls", msg.get("tool_calls"))
        print("finish", data["choices"][0].get("finish_reason"))
        return
    print("status", data.get("status"))
    print("output_types", [item.get("type") for item in data.get("output") or []])
    print("output_text", (data.get("output_text") or "")[:240].replace("\n", " "))
    if data.get("error"):
        print("error", data["error"])


def main() -> None:
    load_env()
    key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API")
    if not key:
        raise SystemExit("missing DEEPSEEK_API_KEY")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    base = "https://api.deepseek.com"
    prompt = "今天北京天气怎么样？请先搜索再回答，一句话。"

    with httpx.Client(timeout=180.0) as client:
        r1 = client.post(
            f"{base}/chat/completions",
            headers=headers,
            json={
                "model": "deepseek-v4-flash",
                "messages": [{"role": "user", "content": prompt}],
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
                "tools": [{"type": "web_search"}],
                "stream": False,
            },
        )
        summarize("chat+thinking+web_search v4-flash", r1)

        r2 = client.post(
            f"{base}/responses",
            headers=headers,
            json={
                "model": "deepseek-v4-flash",
                "input": prompt,
                "tools": [{"type": "web_search"}],
                "reasoning": {"effort": "high"},
            },
        )
        summarize("responses+reasoning+web_search v4-flash", r2)

        r3 = client.post(
            f"{base}/responses",
            headers=headers,
            json={
                "model": "deepseek-v4-flash",
                "input": prompt,
                "tools": [{"type": "web_search"}],
                "reasoning": {"effort": "high"},
            },
        )
        summarize("responses+reasoning+web_search v4-flash", r3)


if __name__ == "__main__":
    main()
