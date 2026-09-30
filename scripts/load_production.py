import argparse
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


def build_payload(idx: int, session_tag: str) -> dict:
    return {
        "user_id": "u_production",
        "session_id": f"{session_tag}-{idx:02d}",
        "feature": "qa",
        "message": f"Production run {idx+1}",
    }


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=["C", "D"], help="C=after-promote, D=after-rollback")
    parser.add_argument("--count", type=int, default=5)
    args = parser.parse_args()

    env = dotenv_values(".env")
    if env.get("LANGFUSE_PROMPT_LABEL") != "production":
        print(f"[FAIL] .env dang co LANGFUSE_PROMPT_LABEL='{env.get('LANGFUSE_PROMPT_LABEL')}', KHONG phai 'production'.")
        sys.exit(1)

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EVIDENCE_DIR / f"production-stage-{args.stage}-trace-ids.jsonl"

    tag = "rb-after-promote" if args.stage == "C" else "rb-after-rollback"
    print(f"[INFO] Stage {args.stage}: session_tag={tag}")

    with httpx.Client(timeout=30.0) as client:
        try:
            client.get(f"{BASE_URL}/health", timeout=5.0).raise_for_status()
        except Exception as exc:
            print(f"[FAIL] API khong healthy: {exc}")
            sys.exit(2)

        for i in range(args.count):
            payload = build_payload(i, tag)
            r = client.post(f"{BASE_URL}/chat", json=payload)
            r.raise_for_status()
            body = r.json()
            cid = body.get("correlation_id", "")
            print(f"[OK] {cid} | session={payload['session_id']}")
            with out_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"stage": args.stage, "label": "production", "correlation_id": cid, "session_id": payload["session_id"], "ts": time.time()}, ensure_ascii=False) + "\n")

    print(f"[DONE] Trace IDs: {out_path}")