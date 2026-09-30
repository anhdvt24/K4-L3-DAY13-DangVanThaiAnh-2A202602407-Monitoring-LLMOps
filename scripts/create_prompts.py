"""Tao prompt 'day13-chat' v1 (label=baseline) va v2 (label=candidate) qua API.

Khong can UI. Chay 1 lan sau khi setup Langfuse project.

Chay: python scripts\create_prompts.py
"""

from __future__ import annotations

from dotenv import dotenv_values
from langfuse import Langfuse


BASELINE_TEXT = (
    "You are a helpful assistant. Answer the user's question concisely.\n"
    "Question: {{question}}"
)

# candidate kha hon baseline mot chut de khi promote co metric cai thien
CANDIDATE_TEXT = (
    "You are a concise support agent for an internal Q&A system.\n"
    "Reply in at most 3 short sentences. If unsure, say 'I don't know'.\n"
    "Question: {{question}}"
)


def main() -> None:
    env = dotenv_values(".env")
    lf = Langfuse(
        public_key=env["LANGFUSE_PUBLIC_KEY"].strip('"'),
        secret_key=env["LANGFUSE_SECRET_KEY"].strip('"'),
        host=env["LANGFUSE_BASE_URL"].strip('"'),
    )

    # v1 = baseline (label ma .env dang tro toi)
    p_baseline = lf.create_prompt(
        name="day13-chat",
        prompt=BASELINE_TEXT,
        labels=["baseline"],  # KHONG them 'production' - de tranh nham voi UI default
        config={"model": "claude-sonnet-4-5", "temperature": 0.0},
        commit_message="v1: baseline prompt",
    )
    print(f"[OK] v1 baseline  -> version={p_baseline.version}")

    # v2 = candidate (dung cho rollback test o buoc sau)
    p_candidate = lf.create_prompt(
        name="day13-chat",
        prompt=CANDIDATE_TEXT,
        labels=["candidate"],
        config={"model": "claude-sonnet-4-5", "temperature": 0.0},
        commit_message="v2: candidate (de rollback test)",
    )
    print(f"[OK] v2 candidate -> version={p_candidate.version}")

    # Verify
    p_v = lf.get_prompt("day13-chat", label="baseline")
    print(f"\n[VERIFY] Fetched by label=baseline: version={p_v.version} labels={p_v.labels}")
    p_v = lf.get_prompt("day13-chat", label="candidate")
    print(f"[VERIFY] Fetched by label=candidate: version={p_v.version} labels={p_v.labels}")


if __name__ == "__main__":
    main()