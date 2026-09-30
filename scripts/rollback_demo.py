"""End-to-end rollback demo cho CP2.

Quy trinh:
  1. Dam bao 2 prompt version da ton tai (chay scripts/create_prompts.py truoc).
  2. Workload voi label=baseline  -> trace v1, label=baseline
  3. Workload voi label=candidate -> trace v2, label=candidate
  4. PROMOTE: gan label 'production' cho v2.
  5. Workload voi label=production -> trace phai co version=2.
  6. ROLLBACK: gan label 'production' lai cho v1.
  7. Workload voi label=production -> trace phai co version=1.

Moi workload ghi 1 dong JSONL vao submission/evidence/rollback-trace-ids.jsonl
de REPORT.md trich ID.

Chay: python scripts\rollback_demo.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values
from langfuse import Langfuse


BASE_URL = "http://127.0.0.1:8000"
EVIDENCE_DIR = Path("submission/evidence")
EVIDENCE_LOG = EVIDENCE_DIR / "rollback-trace-ids.jsonl"


def _wait_for_langfuse_cache(ttl: int = 65) -> None:
    print(f"[wait] Langfuse SDK cache TTL ~{ttl}s. Doi {ttl}s de tranh stale.")
    time.sleep(ttl)


def _ensure_prompts() -> tuple[Langfuse, int, int]:
    """Kiem tra v1 (label=baseline) va v2 (label=candidate) da ton tai chua."""
    env = dotenv_values(".env")
    lf = Langfuse(
        public_key=env["LANGFUSE_PUBLIC_KEY"].strip('"'),
        secret_key=env["LANGFUSE_SECRET_KEY"].strip('"'),
        host=env["LANGFUSE_BASE_URL"].strip('"'),
    )

    try:
        p1 = lf.get_prompt("day13-chat", label="baseline")
        v1 = p1.version
    except Exception as exc:
        print(f"[FAIL] Khong lay duoc prompt label=baseline: {exc}")
        print("       Chay: python scripts\\create_prompts.py")
        sys.exit(2)

    try:
        p2 = lf.get_prompt("day13-chat", label="candidate")
        v2 = p2.version
    except Exception as exc:
        print(f"[FAIL] Khong lay duoc prompt label=candidate: {exc}")
        sys.exit(2)

    print(f"[OK] v1={v1} (label=baseline) | v2={v2} (label=candidate)")
    return lf, v1, v2


def _send_workload(label: str, session_tag: str, count: int = 3) -> list[dict]:
    """Gui count request voi label + session_tag. Tra ve list correlation_id."""
    results: list[dict] = []
    with httpx.Client(timeout=30.0) as client:
        try:
            client.get(f"{BASE_URL}/health", timeout=5.0).raise_for_status()
        except Exception as exc:
            print(f"[FAIL] API khong healthy: {exc}")
            print("       Hay start: uvicorn app.main:app --env-file .env")
            sys.exit(3)

        for i in range(count):
            payload = {
                "user_id": "u_rollback_demo",
                "session_id": f"{session_tag}-{i:02d}",
                "feature": "qa",
                "message": f"[{label}] demo request {i+1}",
            }
            r = client.post(f"{BASE_URL}/chat", json=payload)
            r.raise_for_status()
            body = r.json()
            cid = body.get("correlation_id", "")
            results.append(
                {
                    "label": label,
                    "session_id": payload["session_id"],
                    "correlation_id": cid,
                    "version_in_response": body.get("prompt_version"),  # may be missing
                }
            )
            print(f"  [OK] {label} | {cid} | session={payload['session_id']}")
    return results


def _append_evidence(label: str, stage: str, results: list[dict]) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    with EVIDENCE_LOG.open("a", encoding="utf-8") as f:
        for r in results:
            f.write(
                json.dumps(
                    {
                        "stage": stage,
                        "label": label,
                        "session_id": r["session_id"],
                        "correlation_id": r["correlation_id"],
                        "ts": time.time(),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def _switch_label(lf: Langfuse, version: int, new_label: str) -> None:
    """Gan them 1 label cho 1 version cu the (khong xoa label cu)."""
    try:
        current = lf.get_prompt("day13-chat", version=version)
    except Exception as exc:
        print(f"[FAIL] Khong lay duoc version={version}: {exc}")
        sys.exit(4)
    labels = list(getattr(current, "labels", []))
    if new_label not in labels:
        labels.append(new_label)
        lf.update_prompt(name="day13-chat", version=version, new_labels=labels)
        print(f"  [OK] Gan label '{new_label}' cho v{version}. Labels={labels}")
    else:
        print(f"  [SKIP] v{version} da co label '{new_label}' roi (labels={labels}).")


def _remove_label_from_version(lf: Langfuse, version: int, label: str) -> None:
    """Go label khoi 1 version (khong xoa version)."""
    current = lf.get_prompt("day13-chat", version=version)
    labels = [x for x in getattr(current, "labels", []) if x != label]
    lf.update_prompt(name="day13-chat", version=version, new_labels=labels)
    print(f"  [OK] Go label '{label}' khoi v{version}. Labels={labels}")


def main() -> None:
    print("=" * 60)
    print("CP2 ROLLBACK DEMO")
    print("=" * 60)

    # 0. Reset evidence file (de moi lan chay co log sach)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    if EVIDENCE_LOG.exists():
        EVIDENCE_LOG.unlink()

    # 1. Verify prompts
    lf, v1, v2 = _ensure_prompts()

    # 2. Stage A: workload voi baseline
    print("\n[STAGE A] Workload LABEL=baseline")
    res_a = _send_workload("baseline", "rb-baseline", count=3)
    _append_evidence("baseline", "stage-A", res_a)

    # 3. Stage B: workload voi candidate
    print("\n[STAGE B] Workload LABEL=candidate")
    res_b = _send_workload("candidate", "rb-candidate", count=3)
    _append_evidence("candidate", "stage-B", res_b)

    # 4. Stage C: PROMOTE v2 -> production
    print(f"\n[STAGE C] PROMOTE: gan label 'production' cho v{v2}")
    _switch_label(lf, version=v2, new_label="production")
    _wait_for_langfuse_cache()

    print("\n[STAGE C.2] Workload LABEL=production (sau promote)")
    res_c = _send_workload("production", "rb-after-promote", count=3)
    _append_evidence("production", "stage-C-after-promote", res_c)
    print(f"  -> Trace o stage C phai co prompt_version={v2}")

    # 5. Stage D: ROLLBACK v1 -> production (xoa production khoi v2)
    print(f"\n[STAGE D] ROLLBACK: go 'production' khoi v{v2}, gan lai cho v{v1}")
    _remove_label_from_version(lf, version=v2, label="production")
    _switch_label(lf, version=v1, new_label="production")
    _wait_for_langfuse_cache()

    print("\n[STAGE D.2] Workload LABEL=production (sau rollback)")
    res_d = _send_workload("production", "rb-after-rollback", count=3)
    _append_evidence("production", "stage-D-after-rollback", res_d)
    print(f"  -> Trace o stage D phai co prompt_version={v1}")

    print()
    print("=" * 60)
    print("[DONE] Evidence da ghi vao:", EVIDENCE_LOG)
    print()
    print("Buoc tiep theo:")
    print("  1. Mo Langfuse UI -> Prompts -> day13-chat")
    print("     -> chup anh: v1 (labels=[baseline, production]) + v2 (labels=[candidate])")
    print("     -> luu: submission/evidence/09-prompt-versions.png")
    print("  2. Mo 1 trace stage C -> Metadata -> check prompt_version=", v2)
    print("     -> chup: submission/evidence/10-prompt-rollback.png")
    print("  3. Mo 1 trace stage D -> Metadata -> check prompt_version=", v1)
    print("     -> chup cung 1 anh 10-prompt-rollback.png voi 2 tab so sanh")


if __name__ == "__main__":
    main()