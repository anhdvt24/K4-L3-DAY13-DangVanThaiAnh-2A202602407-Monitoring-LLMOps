"""Cap nhat .env de chuyen LANGFUSE_PROMPT_LABEL.

Su dung: python scripts\\set_prompt_label.py baseline|candidate|production
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"baseline", "candidate", "production"}:
        print("Usage: python scripts\\set_prompt_label.py baseline|candidate|production")
        sys.exit(1)
    new_label = sys.argv[1]
    env_path = Path(".env")
    text = env_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    found = False
    for i, line in enumerate(lines):
        if line.startswith("LANGFUSE_PROMPT_LABEL="):
            lines[i] = f"LANGFUSE_PROMPT_LABEL={new_label}"
            found = True
            break
    if not found:
        lines.append(f"LANGFUSE_PROMPT_LABEL={new_label}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] .env da cap nhat: LANGFUSE_PROMPT_LABEL={new_label}")
    print("     Restart uvicorn de server doc lai env.")


if __name__ == "__main__":
    main()