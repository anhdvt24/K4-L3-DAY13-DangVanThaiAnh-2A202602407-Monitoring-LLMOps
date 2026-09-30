from __future__ import annotations

import math
from collections import Counter
from statistics import mean

REQUEST_LATENCIES: list[int] = []
REQUEST_TTFT: list[int] = []
REQUEST_COSTS: list[float] = []
REQUEST_TOKENS_IN: list[int] = []
REQUEST_TOKENS_OUT: list[int] = []
ERRORS: Counter[str] = Counter()
TRAFFIC: int = 0
QUALITY_SCORES: list[float] = []
TOOL_ATTEMPTS: int = 0
TOOL_SUCCESSES: int = 0


def record_request(
    latency_ms: int,
    ttft_ms: int,
    cost_usd: float,
    tokens_in: int,
    tokens_out: int,
    quality_score: float,
) -> None:
    global TRAFFIC
    TRAFFIC += 1
    REQUEST_LATENCIES.append(latency_ms)
    REQUEST_TTFT.append(ttft_ms)
    REQUEST_COSTS.append(cost_usd)
    REQUEST_TOKENS_IN.append(tokens_in)
    REQUEST_TOKENS_OUT.append(tokens_out)
    QUALITY_SCORES.append(quality_score)


def record_error(error_type: str) -> None:
    ERRORS[error_type] += 1


def record_tool(success: bool) -> None:
    """Ghi nhận một lần tool (retrieval) được gọi và thành công hay không.

    Retrieval success được tính trên TẤT CẢ event có `tool_success`, không chỉ request_failed,
    vì nếu chỉ lấy request_failed thì tỉ lệ luôn 0% (đúng gợi ý CP2).
    """
    global TOOL_ATTEMPTS, TOOL_SUCCESSES
    TOOL_ATTEMPTS += 1
    if success:
        TOOL_SUCCESSES += 1


def percentile(values: list[int | float], p: int) -> float:
    """Percentile theo nearest-rank (NIST).

    Công thức cũ `round((p/100)*len + 0.5) - 1` sai cho P50 với 2 phần tử:
    - [100, 200] trả về 200, không phải 100 (kỳ vọng).
    Nearest-rank dùng `ceil(p/100 * n) - 1` (0-indexed):
    - P50 của [100, 200] = items[ceil(1.0) - 1] = items[0] = 100 ✓
    - P95 của 20 phần tử = items[ceil(0.95*20) - 1] = items[18] (vị trí thứ 19)
    - P100 của n phần tử = items[n-1] (giá trị lớn nhất)
    """
    if not values:
        return 0.0
    items = sorted(values)
    n = len(items)
    # rank 1..n, ceil đảm bảo lấy giá trị thực sự đạt/cận ngưỡng phần trăm
    rank = max(1, min(n, math.ceil(p / 100.0 * n)))
    return float(items[rank - 1])



def snapshot() -> dict:
    retrieval_success_rate = (
        round(100.0 * TOOL_SUCCESSES / TOOL_ATTEMPTS, 2) if TOOL_ATTEMPTS else 0.0
    )
    return {
        "traffic": TRAFFIC,
        "latency_p50": percentile(REQUEST_LATENCIES, 50),
        "latency_p95": percentile(REQUEST_LATENCIES, 95),
        "latency_p99": percentile(REQUEST_LATENCIES, 99),
        "ttft_p95": percentile(REQUEST_TTFT, 95),
        "avg_cost_usd": round(mean(REQUEST_COSTS), 4) if REQUEST_COSTS else 0.0,
        "total_cost_usd": round(sum(REQUEST_COSTS), 4),
        "tokens_in_total": sum(REQUEST_TOKENS_IN),
        "tokens_out_total": sum(REQUEST_TOKENS_OUT),
        "error_breakdown": dict(ERRORS),
        "quality_avg": round(mean(QUALITY_SCORES), 4) if QUALITY_SCORES else 0.0,
        "retrieval_success_rate_pct": retrieval_success_rate,
        "tool_attempts": TOOL_ATTEMPTS,
        "tool_successes": TOOL_SUCCESSES,
    }
