from app.metrics import percentile, record_request, record_tool, snapshot


def test_percentile_basic() -> None:
    assert percentile([100, 200, 300, 400], 50) >= 100


def test_record_tool_computes_retrieval_success_rate(monkeypatch) -> None:
    # Reset global state trong module để test độc lập với thứ tự chạy.
    import app.metrics as metrics_module

    monkeypatch.setattr(metrics_module, "TOOL_ATTEMPTS", 0)
    monkeypatch.setattr(metrics_module, "TOOL_SUCCESSES", 0)
    monkeypatch.setattr(metrics_module, "REQUEST_LATENCIES", [])
    monkeypatch.setattr(metrics_module, "REQUEST_TTFT", [])
    monkeypatch.setattr(metrics_module, "REQUEST_COSTS", [])
    monkeypatch.setattr(metrics_module, "REQUEST_TOKENS_IN", [])
    monkeypatch.setattr(metrics_module, "REQUEST_TOKENS_OUT", [])
    monkeypatch.setattr(metrics_module, "ERRORS", metrics_module.ERRORS.__class__())
    monkeypatch.setattr(metrics_module, "TRAFFIC", 0)
    monkeypatch.setattr(metrics_module, "QUALITY_SCORES", [])

    record_tool(True)
    record_tool(True)
    record_tool(False)
    record_tool(True)

    snap = snapshot()
    assert snap["tool_attempts"] == 4
    assert snap["tool_successes"] == 3
    # Tỉ lệ 3/4 = 75%; phải là phần trăm.
    assert snap["retrieval_success_rate_pct"] == 75.0


def test_record_request_updates_traffic_and_latency(monkeypatch) -> None:
    import app.metrics as metrics_module

    monkeypatch.setattr(metrics_module, "TOOL_ATTEMPTS", 0)
    monkeypatch.setattr(metrics_module, "TOOL_SUCCESSES", 0)
    monkeypatch.setattr(metrics_module, "REQUEST_LATENCIES", [])
    monkeypatch.setattr(metrics_module, "REQUEST_TTFT", [])
    monkeypatch.setattr(metrics_module, "REQUEST_COSTS", [])
    monkeypatch.setattr(metrics_module, "REQUEST_TOKENS_IN", [])
    monkeypatch.setattr(metrics_module, "REQUEST_TOKENS_OUT", [])
    monkeypatch.setattr(metrics_module, "ERRORS", metrics_module.ERRORS.__class__())
    monkeypatch.setattr(metrics_module, "TRAFFIC", 0)
    monkeypatch.setattr(metrics_module, "QUALITY_SCORES", [])

    record_request(latency_ms=100, ttft_ms=50, cost_usd=0.001, tokens_in=10, tokens_out=20, quality_score=0.8)
    record_request(latency_ms=200, ttft_ms=80, cost_usd=0.002, tokens_in=15, tokens_out=25, quality_score=0.9)

    snap = snapshot()
    assert snap["traffic"] == 2
    assert snap["latency_p50"] == 100  # trung vị của [100, 200]
    assert snap["tokens_in_total"] == 25
    assert snap["tokens_out_total"] == 45
