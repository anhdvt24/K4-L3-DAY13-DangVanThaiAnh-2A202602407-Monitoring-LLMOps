"""Quan ly label 'production' cho prompt day13-chat.

Mode:
  status   - in ra v1, v2 va label hien tai
  promote  - gan them label 'production' cho v2 (candidate), KHONG xoa khoi v1
  rollback - go label 'production' khoi v2 (candidate), gan lai cho v1

Chay:
  python scripts\\manage_label.py status
  python scripts\\manage_label.py promote
  python scripts\\manage_label.py rollback
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import dotenv_values
from langfuse import Langfuse


def _client() -> Langfuse:
    env = dotenv_values(".env")
    return Langfuse(
        public_key=env["LANGFUSE_PUBLIC_KEY"].strip('"'),
        secret_key=env["LANGFUSE_SECRET_KEY"].strip('"'),
        host=env["LANGFUSE_BASE_URL"].strip('"'),
    )


def _find_versions(lf: Langfuse) -> tuple[int, int]:
    p1 = lf.get_prompt("day13-chat", label="baseline")
    p2 = lf.get_prompt("day13-chat", label="candidate")
    return p1.version, p2.version


def cmd_status() -> None:
    lf = _client()
    v1, v2 = _find_versions(lf)
    p1 = lf.get_prompt("day13-chat", version=v1)
    p2 = lf.get_prompt("day13-chat", version=v2)
    print(f"v{v1} labels={list(p1.labels)}")
    print(f"v{v2} labels={list(p2.labels)}")


def _set_labels(lf: Langfuse, version: int, keep: list[str]) -> None:
    # 'latest' la label mac dinh cua SDK; khong the gan thu cong qua update_prompt.
    # API se reject neu newLabels chua 'latest'. Bo no truoc khi gui.
    keep = [x for x in keep if x != "latest"]
    lf.update_prompt(name="day13-chat", version=version, new_labels=keep)
    p = lf.get_prompt("day13-chat", version=version)
    print(f"  [OK] v{version} labels={list(p.labels)}")


def cmd_promote() -> None:
    lf = _client()
    v1, v2 = _find_versions(lf)
    print(f"[PROMOTE] Them 'production' cho v{v2}; KHONG xoa khoi v{v1} (rollback de go)")
    p2 = lf.get_prompt("day13-chat", version=v2)
    labels = list(p2.labels)
    if "production" not in labels:
        labels.append("production")
        _set_labels(lf, v2, labels)
    else:
        print(f"  [SKIP] v{v2} da co 'production' (labels={labels}).")


def cmd_rollback() -> None:
    lf = _client()
    v1, v2 = _find_versions(lf)
    print(f"[ROLLBACK] Xoa 'production' khoi v{v2}; them vao v{v1}")
    p2 = lf.get_prompt("day13-chat", version=v2)
    labels2 = [x for x in p2.labels if x != "production"]
    _set_labels(lf, v2, labels2)
    p1 = lf.get_prompt("day13-chat", version=v1)
    labels1 = list(p1.labels)
    if "production" not in labels1:
        labels1.append("production")
        _set_labels(lf, v1, labels1)
    else:
        print(f"  [SKIP] v{v1} da co 'production' (labels={labels1}).")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"status", "promote", "rollback"}:
        print(__doc__)
        sys.exit(1)
    cmd = {"status": cmd_status, "promote": cmd_promote, "rollback": cmd_rollback}[sys.argv[1]]
    cmd()
    sys.stdout.flush()