"""Verify prompt da duoc fetch tu Langfuse (khong phai local fallback).

Chay: python scripts\verify_prompt_source.py
Output: in ra prompt_name, label, version, source, fetch_error.
        Thoat code 0 neu source='langfuse', 1 neu bi fallback.
"""

from __future__ import annotations

import os
import sys

from dotenv import dotenv_values


def main() -> None:
    env = dotenv_values(".env")
    name = env.get("LANGFUSE_PROMPT_NAME", "day13-chat")
    label = env.get("LANGFUSE_PROMPT_LABEL", "baseline")

    from langfuse import Langfuse

    lf = Langfuse(
        public_key=env["LANGFUSE_PUBLIC_KEY"].strip('"'),
        secret_key=env["LANGFUSE_SECRET_KEY"].strip('"'),
        host=env["LANGFUSE_BASE_URL"].strip('"'),
    )

    try:
        p = lf.get_prompt(name, label=label, type="text")
    except Exception as exc:
        print(f"[FAIL] Khong fetch duoc prompt '{name}' (label={label}): {exc}")
        sys.exit(2)

    is_fallback = getattr(p, "is_fallback", False)
    print(f"name           = {p.name}")
    print(f"label          = {label}")
    print(f"version        = {p.version}")
    print(f"is_fallback    = {is_fallback}")
    print(f"prompt length  = {len(p.prompt)} chars")
    print(f"first 80 chars = {p.prompt[:80]!r}")

    if is_fallback:
        print()
        print("[WARN] Dang dung FALLBACK (khong lay duoc prompt that tu Langfuse).")
        print("       - Prompt 'day13-chat' chua duoc tao?")
        print("       - API key sai project?")
        print("       - Ten/label khong match?")
        sys.exit(1)

    print()
    print("[OK] Prompt that tu Langfuse (khong phai fallback).")


if __name__ == "__main__":
    main()