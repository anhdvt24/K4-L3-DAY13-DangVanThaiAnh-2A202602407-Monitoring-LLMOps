"""Dashboard runtime cho Day 13 Monitoring & LLMOps.

Đọc data/logs.jsonl, tính các chỉ số theo contract trong config/dashboard.yaml
và xuất 6 panel PNG vào submission/evidence/. Mỗi panel có tên, đơn vị, time range
60 phút và đường threshold khi contract quy định.

Cài matplotlib một lần:
    
    
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
EVIDENCE_DIR = REPO_ROOT / "submission" / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

# Threshold từ config/dashboard.yaml, dùng để vẽ đường SLO.
THRESHOLDS = {
    "latency": {"aggregation": "p95", "operator": "lte", "value": 3000, "unit": "ms"},
    "traffic": {"aggregation": "rate_per_minute", "operator": "gte", "value": 1, "unit": "req/min"},
    "errors": {"aggregation": "error_rate_pct", "operator": "lte", "value": 2, "unit": "%"},
    "cost": {"aggregation": "total", "operator": "lte", "value": 2.5, "unit": "USD"},
    "tokens": {"aggregation": "sum_by_field", "operator": "lte", "value": 50000, "unit": "tokens"},
    "quality": {"aggregation": "mean", "operator": "gte", "value": 0.75, "unit": "score"},
}


def percentile(values: list[int | float], p: int) -> float:
    if not values:
        return 0.0
    items = sorted(values)
    idx = max(0, min(len(items) - 1, round((p / 100) * len(items) + 0.5) - 1))
    return float(items[idx])


def load_records() -> list[dict]:
    if not LOG_PATH.exists():
        print(f"[warn] {LOG_PATH} chưa tồn tại. Hãy chạy load_test.py trước.")
        return []
    records = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def parse_ts(rec: dict) -> datetime | None:
    ts = rec.get("ts")
    if not ts:
        return None
    try:
        # Langfuse/structlog trả ISO8601; thay Z bằng +00:00 để fromisoformat hiểu.
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def draw_threshold(ax, threshold: dict, unit: str) -> None:
    """Vẽ đường ngang SLO/threshold theo operator/value."""
    if not threshold:
        return
    value = threshold["value"]
    if threshold["operator"] == "lte":
        ax.axhline(value, color="red", linestyle="--", linewidth=1, label=f"SLO ≤ {value} {unit}")
    else:  # gte
        ax.axhline(value, color="red", linestyle="--", linewidth=1, label=f"SLO ≥ {value} {unit}")


def panel_latency(records: list[dict]) -> None:
    response = [r for r in records if r.get("event") == "response_sent"]
    if not response:
        return
    response.sort(key=lambda r: r["ts_dt"])
    latencies = [r.get("latency_ms", 0) for r in response]
    ttfts = [r.get("ttft_ms", 0) for r in response]

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot([r["ts_dt"] for r in response], latencies, marker="o", label="latency_ms (per req)")
    ax.set_title("Panel: Latency P50/P95/P99 & TTFT (last 60 min)")
    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("Latency / TTFT (ms)")
    ax.grid(True, alpha=0.3)

    # Vẽ percentile lines (P50/P95/P99) của latency.
    p50 = percentile(latencies, 50)
    p95 = percentile(latencies, 95)
    p99 = percentile(latencies, 99)
    ttft_p95 = percentile(ttfts, 95)
    ax.axhline(p50, color="green", linestyle=":", linewidth=1, label=f"P50={p50:.0f}ms")
    ax.axhline(p95, color="orange", linestyle=":", linewidth=1, label=f"P95={p95:.0f}ms")
    ax.axhline(p99, color="red", linestyle=":", linewidth=1, label=f"P99={p99:.0f}ms")
    ax.axhline(ttft_p95, color="purple", linestyle="-.", linewidth=1, label=f"TTFT P95={ttft_p95:.0f}ms")
    draw_threshold(ax, THRESHOLDS["latency"], "ms")
    ax.legend(loc="upper left", fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(EVIDENCE_DIR / "panel-latency.png", dpi=120)
    plt.close(fig)


def panel_traffic(records: list[dict]) -> None:
    received = [r for r in records if r.get("event") == "request_received"]
    if not received:
        return
    received.sort(key=lambda r: r["ts_dt"])
    times = [r["ts_dt"] for r in received]

    # Group theo phút
    per_minute: dict[datetime, int] = {}
    for t in times:
        bucket = t.replace(second=0, microsecond=0)
        per_minute[bucket] = per_minute.get(bucket, 0) + 1
    xs = sorted(per_minute.keys())
    ys = [per_minute[x] for x in xs]

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(xs, ys, width=0.012, color="steelblue", alpha=0.85)
    ax.set_title("Panel: Traffic — requests per minute (last 60 min)")
    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("Requests / minute")
    ax.grid(True, alpha=0.3)
    draw_threshold(ax, THRESHOLDS["traffic"], "req/min")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(EVIDENCE_DIR / "panel-traffic.png", dpi=120)
    plt.close(fig)


def panel_errors(records: list[dict]) -> None:
    failed = [r for r in records if r.get("event") == "request_failed"]
    received = [r for r in records if r.get("event") == "request_received"]
    total_requests = len(received) or len(failed) or 1
    error_rate_pct = 100.0 * len(failed) / total_requests

    # Retrieval success: trên TẤT CẢ event có field tool_success (response_sent + request_failed)
    # theo gợi ý trong hướng dẫn CP2.
    tool_events = [r for r in records if "tool_success" in r]
    if tool_events:
        retrieval_success_pct = 100.0 * sum(1 for r in tool_events if r.get("tool_success")) / len(tool_events)
    else:
        retrieval_success_pct = 0.0

    error_types: dict[str, int] = {}
    for f in failed:
        et = f.get("error_type", "Unknown")
        error_types[et] = error_types.get(et, 0) + 1

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
    ax1.bar(["Error rate", "Retrieval success"], [error_rate_pct, retrieval_success_pct], color=["#d9534f", "#5cb85c"])
    ax1.set_title("Panel: Errors & retrieval success")
    ax1.set_ylabel("Percent (%)")
    ax1.set_ylim(0, 100)
    ax1.axhline(THRESHOLDS["errors"]["value"], color="red", linestyle="--", linewidth=1, label=f"Error SLO ≤ {THRESHOLDS['errors']['value']}%")
    ax1.legend(fontsize=8)
    for label, val in zip(["Error rate", "Retrieval success"], [error_rate_pct, retrieval_success_pct]):
        ax1.text(label, val + 2, f"{val:.1f}%", ha="center", fontsize=9)
    ax1.grid(True, alpha=0.3)

    if error_types:
        ax2.bar(list(error_types.keys()), list(error_types.values()), color="salmon")
        ax2.set_title("Error breakdown by error_type")
        ax2.set_xlabel("error_type")
        ax2.set_ylabel("Count")
        ax2.grid(True, alpha=0.3)
    else:
        ax2.text(0.5, 0.5, "No errors recorded", ha="center", va="center")
        ax2.set_axis_off()

    fig.tight_layout()
    fig.savefig(EVIDENCE_DIR / "panel-errors.png", dpi=120)
    plt.close(fig)


def panel_cost(records: list[dict]) -> None:
    response = [r for r in records if r.get("event") == "response_sent"]
    if not response:
        return
    response.sort(key=lambda r: r["ts_dt"])
    per_minute: dict[datetime, float] = {}
    for r in response:
        bucket = r["ts_dt"].replace(second=0, microsecond=0)
        per_minute[bucket] = per_minute.get(bucket, 0.0) + float(r.get("cost_usd", 0))

    xs = sorted(per_minute.keys())
    ys = [per_minute[x] for x in xs]
    total = sum(ys)

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(xs, ys, marker="o", color="darkorange", label="USD/min")
    ax.fill_between(xs, ys, alpha=0.2, color="orange")
    ax.set_title(f"Panel: Cost over time — total ${total:.4f} (last 60 min)")
    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("Cost (USD)")
    ax.grid(True, alpha=0.3)
    draw_threshold(ax, THRESHOLDS["cost"], "USD")
    ax.legend(loc="upper left", fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(EVIDENCE_DIR / "panel-cost.png", dpi=120)
    plt.close(fig)


def panel_tokens(records: list[dict]) -> None:
    response = [r for r in records if r.get("event") == "response_sent"]
    if not response:
        return
    total_in = sum(r.get("tokens_in", 0) for r in response)
    total_out = sum(r.get("tokens_out", 0) for r in response)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(["tokens_in", "tokens_out"], [total_in, total_out], color=["#337ab7", "#5cb85c"])
    ax.set_title(f"Panel: Input/output tokens — total {total_in + total_out}")
    ax.set_ylabel("Tokens")
    ax.grid(True, alpha=0.3)
    for label, val in zip(["tokens_in", "tokens_out"], [total_in, total_out]):
        ax.text(label, val + max(total_in, total_out) * 0.02, f"{val:,}", ha="center", fontsize=9)
    draw_threshold(ax, THRESHOLDS["tokens"], "tokens")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(EVIDENCE_DIR / "panel-tokens.png", dpi=120)
    plt.close(fig)


def panel_quality(records: list[dict]) -> None:
    response = [r for r in records if r.get("event") == "response_sent"]
    if not response:
        return
    response.sort(key=lambda r: r["ts_dt"])
    scores = [float(r.get("quality_score", 0)) for r in response]
    avg = sum(scores) / len(scores)

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot([r["ts_dt"] for r in response], scores, marker="o", color="green", label="quality_score")
    ax.axhline(avg, color="green", linestyle=":", linewidth=1, label=f"mean={avg:.2f}")
    ax.set_ylim(0, 1)
    ax.set_title(f"Panel: Quality proxy — mean {avg:.2f} (last 60 min)")
    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("quality_score (0..1)")
    ax.grid(True, alpha=0.3)
    draw_threshold(ax, THRESHOLDS["quality"], "score")
    ax.legend(loc="lower left", fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(EVIDENCE_DIR / "panel-quality.png", dpi=120)
    plt.close(fig)


def build_combined_overview(panels: list[Path]) -> None:
    """Ghép 6 panel thành 1 ảnh tổng quan (11-dashboard-overview.png) để nộp evidence."""
    from PIL import Image

    images = [Image.open(p) for p in panels if p.exists()]
    if not images:
        return
    cols = 2
    rows = (len(images) + cols - 1) // cols
    w, h = images[0].size
    combined = Image.new("RGB", (w * cols, h * rows), "white")
    for idx, img in enumerate(images):
        r, c = divmod(idx, cols)
        combined.paste(img, (c * w, r * h))
    combined.save(EVIDENCE_DIR / "11-dashboard-overview.png", dpi=(120, 120))


def main() -> None:
    records = load_records()
    if not records:
        return

    # Chuẩn hoá timestamp về datetime để matplotlib sort/vẽ.
    for r in records:
        dt = parse_ts(r)
        if dt is None:
            continue
        # Lọc theo time_range_minutes=60
        r["ts_dt"] = dt
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=60)
    records = [r for r in records if "ts_dt" in r and r["ts_dt"] >= window_start]
    records.sort(key=lambda r: r["ts_dt"])

    panel_latency(records)
    panel_traffic(records)
    panel_errors(records)
    panel_cost(records)
    panel_tokens(records)
    panel_quality(records)

    panels = [
        EVIDENCE_DIR / "panel-latency.png",
        EVIDENCE_DIR / "panel-traffic.png",
        EVIDENCE_DIR / "panel-errors.png",
        EVIDENCE_DIR / "panel-cost.png",
        EVIDENCE_DIR / "panel-tokens.png",
        EVIDENCE_DIR / "panel-quality.png",
    ]
    build_combined_overview(panels)
    print(f"Đã tạo {len(panels)} panel + 11-dashboard-overview.png trong {EVIDENCE_DIR}")


if __name__ == "__main__":
    main()
