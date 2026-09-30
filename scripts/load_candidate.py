"""Workload chay voi LANGFUSE_PROMPT_LABEL=candidate.

Yeu cau: server da restart voi LANGFUSE_PROMPT_LABEL=candidate.
Chay: python scripts\\load_candidate.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.cli import configure_utf8_stdio  # noqa: E402

BASE_URL = "http://127.0.0.1:8000"
EVIDENCE_DIR = Path("submission/evidence")


def build_payload(idx: int) -> dict:
    messages = [
        "Refunds within 7 days require proof of purchase.",
        "What is cost optimization for LLM apps?",
        "Show me how to monitor latency.",
        "Explain trace waterfall.",
        "Why is my dashboard empty?",
    ]
    return {
        "user_id": "u_candidate",
        "session_id": f"candidate-session-{idx:02d}",
        "feature": "qa",
        "message": messages[idx % len(messages)],
    }


def main() -> None:
    configure_utf8_stdio()
    env = dotenv_values(".env")
    if env.get("LANGFUSE_PROMPT_LABEL") != "candidate":
        print(f"[WARN] .env dang co LANGFUSE_PROMPT_LABEL='{env.get('LANGFUSE_PROMPT_LABEL')}', KHONG phai 'candidate'.")
        print("        Chay: python scripts\\set_prompt_label.py candidate")
        print("        Roi restart uvicorn.")
        sys.exit(1)

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EVIDENCE_DIR / "candidate-trace-ids.jsonl"

    with httpx.Client(timeout=30.0) as client:
        try:
            client.get(f"{BASE_URL}/health", timeout=5.0).raise_for_status()
        except Exception as exc:
            print(f"[FAIL] API khong healthy: {exc}")
            sys.exit(2)

        for i in range(5):
            payload = build_payload(i)
            t0 = time.perf_counter()
            r = client.post(f"{BASE_URL}/chat", json=payload)
            latency_ms = (time.perf_counter() - t0) * 1000
            r.raise_for_status()
            body = r.json()
            cid = body.get("correlation_id", "")
            print(f"[OK] {cid} | session={payload['session_id']} | latency={latency_ms:.1f}ms")
            with out_path.open("a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "label": "candidate",
                            "correlation_id": cid,
                            "session_id": payload["session_id"],
                            "ts": time.time(),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    print()
    print(f"[DONE] Trace IDs ghi vao: {out_path}")
    print("       Filter Langfuse UI theo session_id='candidate-session-*' de xem.")


if __name__ == "__main__":
    main()