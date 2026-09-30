"""Sinh evidence text cho rubric: chạy pytest, validate_logs, validate_dashboard,
lấy 1 dòng structured log và minh họa PII redaction.

Mỗi output được ghi vào submission/evidence/<name>.txt, đính kèm header ghi rõ
lệnh đã chạy, thời gian, môi trường. Sau khi chạy xong, bạn có thể paste text
vào ảnh chụp terminal hoặc nộp trực tiếp file .txt (rubric chấp nhận cả hai).

Chạy:
    python scripts/collect_evidence.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = REPO_ROOT / "submission" / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

# Thêm repo root vào sys.path để script gọi được `from app.pii import ...`
# khi chạy từ bất kỳ thư mục nào.
sys.path.insert(0, str(REPO_ROOT))

# Đường dẫn tới venv Python nếu có; fallback về sys.executable.
VENV_PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Chạy lệnh và trả về (returncode, stdout, stderr)."""
    proc = subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def write_evidence(name: str, header: str, body: str) -> Path:
    """Ghi file evidence .txt kèm header để chấm rõ nguồn gốc."""
    path = EVIDENCE_DIR / f"{name}.txt"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = f"""# Evidence: {name}
# Generated: {ts}
# Working dir: {REPO_ROOT}
# Python: {PYTHON}

{header}

{body.strip()}

# End of evidence
"""
    path.write_text(payload, encoding="utf-8")
    return path


def collect_pytest() -> None:
    rc, out, err = run([PYTHON, "-m", "pytest", "-q"])
    body = out + ("\n--- stderr ---\n" + err if err else "")
    write_evidence(
        "01-pytest",
        f"# Command: {PYTHON} -m pytest -q\n# Return code: {rc}",
        body,
    )


def collect_log_validator() -> None:
    rc, out, err = run([PYTHON, "scripts/validate_logs.py"])
    body = out + ("\n--- stderr ---\n" + err if err else "")
    write_evidence(
        "02-log-validator",
        f"# Command: {PYTHON} scripts/validate_logs.py\n# Return code: {rc}",
        body,
    )


def collect_dashboard_validator() -> None:
    rc, out, err = run([PYTHON, "scripts/validate_dashboard.py"])
    body = out + ("\n--- stderr ---\n" + err if err else "")
    write_evidence(
        "03-dashboard-validator",
        f"# Command: {PYTHON} scripts/validate_dashboard.py\n# Return code: {rc}",
        body,
    )


def collect_structured_log() -> None:
    """Lấy 1 dòng request_received và 1 dòng response_sent từ data/logs.jsonl
    để chứng minh log có đủ field bắt buộc + correlation_id + metadata."""
    log_path = REPO_ROOT / "data" / "logs.jsonl"
    if not log_path.exists():
        write_evidence(
            "04-structured-log",
            "# data/logs.jsonl không tồn tại. Hãy chạy uvicorn + load_test.py trước.",
            "",
        )
        return
    samples: list[str] = []
    request_seen = False
    response_seen = False
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not request_seen and rec.get("event") == "request_received":
            samples.append(json.dumps(rec, ensure_ascii=False, indent=2))
            request_seen = True
        elif not response_seen and rec.get("event") == "response_sent":
            samples.append(json.dumps(rec, ensure_ascii=False, indent=2))
            response_seen = True
        if request_seen and response_seen:
            break
    if not samples:
        write_evidence("04-structured-log", "# Không tìm thấy event request_received / response_sent", "")
        return
    header = (
        "# Source: data/logs.jsonl\n"
        "# Lấy mẫu: 1 request_received + 1 response_sent gần nhất\n"
        "# Các trường bắt buộc phải có: ts, level, service, event, correlation_id, "
        "user_id_hash, session_id, feature, model\n"
    )
    body = "\n\n--- log record ---\n\n".join(samples)
    write_evidence("04-structured-log", header, body)


def collect_pii_redaction() -> None:
    """Test in-process: gửi request chứa PII giả, in ra log trước và sau scrub.

    Cách làm: gọi LabAgent.run với message có email + phone + CCCD + card.
    Sau đó in ra:
      - input raw (chứa PII)
      - preview sau khi qua summarize_text() — đây là dữ liệu thực sự ghi vào log.
    """
    # Import trong script để tránh phụ thuộc khi không chạy evidence
    try:
        from app.pii import scrub_text, summarize_text
    except Exception as e:
        write_evidence("05-pii-redaction", f"# Lỗi import app.pii: {e}", "")
        return

    raw_samples = [
        "My email is student@vinuni.edu.vn",
        "Phone: 090 123 4567 hoặc +84 90 555 1234",
        "CCCD: 012345678901",
        "Credit card: 4111 1111 1111 1111",
        "Mix: liên hệ an@bank.com hoặc 0987.654.321, CCCD 123456789012, card 5500 0000 0000 0004",
    ]

    lines: list[str] = []
    lines.append("# Test PII scrubbing trong app/pii.py")
    lines.append("# Mỗi cặp dòng: RAW (input) | REDACTED (output qua summarize_text)")
    lines.append("")
    for raw in raw_samples:
        scrubbed = summarize_text(raw, max_len=120)
        lines.append(f"RAW      : {raw}")
        lines.append(f"REDACTED : {scrubbed}")
        # Kiểm tra nhanh: các pattern không được xuất hiện nguyên văn
        assert "student@vinuni.edu.vn" not in scrubbed
        assert "012345678901" not in scrubbed
        assert "4111 1111 1111 1111" not in scrubbed
        lines.append("---")
    body = "\n".join(lines)
    write_evidence(
        "05-pii-redaction",
        "# Source: chạy scrub_text() / summarize_text() từ app/pii.py trên input mẫu.\n"
        "# Nếu bạn muốn ảnh PNG: chạy thêm request qua API rồi xem data/logs.jsonl.",
        body,
    )


def main() -> None:
    print(f"Python: {PYTHON}")
    print(f"Evidence dir: {EVIDENCE_DIR}")
    collect_pytest()
    print("[OK] 01-pytest.txt")
    collect_log_validator()
    print("[OK] 02-log-validator.txt")
    collect_dashboard_validator()
    print("[OK] 03-dashboard-validator.txt")
    collect_structured_log()
    print("[OK] 04-structured-log.txt")
    collect_pii_redaction()
    print("[OK] 05-pii-redaction.txt")
    print()
    print("Ban co the:")
    print("  1. Mo tung file .txt, chup anh terminal -> luu PNG cung ten.")
    print("  2. Hoacnop truc tiep file .txt (rubric chap nhan ca .txt).")


if __name__ == "__main__":
    main()