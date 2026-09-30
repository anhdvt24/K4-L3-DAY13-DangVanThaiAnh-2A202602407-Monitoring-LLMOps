"""Workload cho CP2 baseline: gửi 10 request với LANGFUSE_PROMPT_LABEL=baseline.

Mục tiêu: tạo >=10 trace trên Langfuse để kiểm tra metadata prompt_name/label/version.

Cách dùng:
    1. Đảm bảo .env đang có LANGFUSE_PROMPT_LABEL=baseline.
    2. Đảm bảo uvicorn đang chạy tại http://127.0.0.1:8000.
    3. (Khuyến nghị) Khởi động lại API để clear cache prompt 60s.
    4. Chạy: python scripts/load_baseline.py
    5. Mở Langfuse UI -> Traces -> filter theo metadata.user_id_hash=<x>
       hoặc session_id=baseline-session-01.
    6. Click vào span lab-agent-run -> tab Metadata:
       prompt_name=day13-chat, prompt_label=baseline, prompt_version=1
       (giả định bạn đã tạo version 1 trên UI trước đó).

Output: in ra correlation_id của từng request để bạn copy vào REPORT.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio

BASE_URL = "http://127.0.0.1:8000"


def build_payload(idx: int, feature: str = "qa") -> dict:
    """Payload mẫu cho baseline. user_id/session_id đặc biệt để filter dễ trên Langfuse."""
    messages = [
        "What is the refund policy?",
        "Explain how traces work in monitoring.",
        "What counts as PII in logs?",
        "How is error rate calculated?",
        "What does the latency p95 metric mean?",
        "How do I rollback a prompt version?",
        "What is the cost guardrail threshold?",
        "Why are my dashboard panels empty?",
        "How do retrieval spans appear in traces?",
        "What does correlation_id do in the trace?",
    ]
    return {
        "user_id": "u_baseline",
        "session_id": f"baseline-session-{idx:02d}",
        "feature": feature,
        "message": messages[idx % len(messages)],
    }


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=10, help="Số request cần gửi (mặc định 10).")
    parser.add_argument("--feature", type=str, default="qa", help="feature cho mỗi request.")
    parser.add_argument(
        "--out",
        type=str,
        default="submission/evidence/baseline-trace-ids.jsonl",
        help="File để ghi correlation_id từng request.",
    )
    args = parser.parse_args()

    out_path = REPO_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    correlation_ids: list[str] = []
    with httpx.Client(timeout=30.0) as client:
        # Health check trước
        try:
            health = client.get(f"{BASE_URL}/health", timeout=5.0)
            health.raise_for_status()
            print(f"[OK] API healthy: {health.json()}")
        except Exception as e:
            print(f"[FAIL] Khong ket noi API tai {BASE_URL}: {e}")
            print("Hay start uvicorn truoc:")
            print("  uvicorn app.main:app --reload --env-file .env")
            sys.exit(1)

        for i in range(args.count):
            payload = build_payload(i, feature=args.feature)
            t0 = time.perf_counter()
            try:
                r = client.post(f"{BASE_URL}/chat", json=payload)
                latency_ms = (time.perf_counter() - t0) * 1000
                r.raise_for_status()
                body = r.json()
                cid = body.get("correlation_id", "")
                correlation_ids.append(cid)
                print(
                    f"[{r.status_code}] {cid} | {payload['feature']} | "
                    f"latency={latency_ms:.1f}ms | tokens_in={body.get('tokens_in')} "
                    f"tokens_out={body.get('tokens_out')} | session={payload['session_id']}"
                )
                with out_path.open("a", encoding="utf-8") as f:
                    f.write(
                        json.dumps(
                            {
                                "label": "baseline",
                                "correlation_id": cid,
                                "session_id": payload["session_id"],
                                "feature": payload["feature"],
                                "latency_ms": round(latency_ms, 1),
                                "tokens_in": body.get("tokens_in"),
                                "tokens_out": body.get("tokens_out"),
                                "cost_usd": body.get("cost_usd"),
                                "ts": time.time(),
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
            except Exception as e:
                print(f"[ERR] {payload['session_id']}: {e}")

    # Flush hint
    print()
    print("=" * 60)
    print(f"Da gui {len(correlation_ids)}/{args.count} request thanh cong.")
    print("DOI 5-10 GIAY de Langfuse SDK flush batch truoc khi restart/stop API.")
    print(f"Correlation IDs da ghi vao: {out_path}")
    print()
    print("Buoc tiep theo:")
    print("  1. Mo Langfuse UI -> Traces -> filter theo user_id_hash=user_id hash cua 'u_baseline'")
    print("     (Langfuse tu hash qua hash_user_id; hoac search theo tag=lab)")
    print("  2. Mo 1 trace -> click span 'lab-agent-run' -> tab Metadata:")
    print("     prompt_name=day13-chat, prompt_label=baseline, prompt_version=1")
    print("  3. Copy trace ID dau tien vao REPORT.md (baseline).")


if __name__ == "__main__":
    main()
