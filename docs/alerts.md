# Runbook cho 3 Alert Day 13

Mỗi alert phải dựa trên triệu chứng quan sát được từ user/SLO, không dựa trực tiếp vào tên implementation nội bộ. Khi alert bắn, người trực đi theo ba bước kiểm tra **Metrics → Logs → Traces**, rồi mitigation tạm thời.

> Quy ước: tất cả lệnh trong runbook chạy trên máy local, với API đang chạy tại `http://127.0.0.1:8000` và đã có key Langfuse trong `.env`. Log dashboard là `data/logs.jsonl`.

## Alert 1: High Latency P95

- **Tên:** `HighLatencyP95`
- **Severity:** `warning`
- **Duration:** `5m`
- **Kênh thông báo:** Slack `#k4-l3b-alerts`
- **SLI/SLO liên quan:** latency P95 của `response_sent.latency_ms` (SLO 99.5% request có `latency_ms <= 3000`)
- **Điều kiện và thời gian duy trì:** `p95(latency_ms) > 3000ms` trong 5 phút liên tiếp
- **Ảnh hưởng tới người dùng:** người dùng phải chờ lâu hơn trước khi nhận câu trả lời; tỉ lệ thoát (drop-off) có thể tăng
- **Ba bước kiểm tra đầu tiên:**
  1. Mở dashboard panel **Latency**, xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó (`jq 'select(.event=="response_sent" and .latency_ms>3000)'`), lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse (project cá nhân), so sánh các span `retrieval` vs `generation` để xác định bước nào chiếm phần lớn thời gian.
- **Mitigation tạm thời:**
  - Nếu span `retrieval` chiếm phần lớn: tắt practice scenario RAG (nếu đang bật): `python scripts/inject_incident.py --scenario rag_slow --disable`. Trong production thật: kiểm tra vector store, tăng timeout hoặc bật cache.
  - Nếu span `generation` chiếm phần lớn: kiểm tra prompt version hiện tại; rollback `production` về version cũ nếu prompt mới dài bất thường (xem CP2 6.2). Nếu LLM provider có vấn đề, chuyển sang provider dự phòng hoặc giảm `max_tokens`.
  - Nếu span retrieval OK, generation OK, latency vẫn cao → kiểm tra tài nguyên máy (CPU, RAM), uvicorn worker count.
- **Owner:** `student-<MSSV>`

## Alert 2: Retrieval Success Drop

- **Tên:** `RetrievalSuccessDrop`
- **Severity:** `warning`
- **Duration:** `10m`
- **Kênh thông báo:** Slack `#k4-l3b-alerts`
- **SLI/SLO liên quan:** retrieval success rate (guardrail `retrieval_success_rate_pct_min: 90`)
- **Điều kiện và thời gian duy trì:** `retrieval_success_rate_pct < 90%` trong 10 phút liên tiếc
- **Ảnh hưởng tới người dùng:** câu trả lời dùng fallback "No domain document matched" hoặc lỗi 500; chất lượng giảm rõ rệt
- **Ba bước kiểm tra đầu tiên:**
  1. Mở dashboard panel **Errors**, kiểm tra tỉ lệ `tool_success=true` đang giảm hay `error_rate_pct` đang tăng.
  2. Lọc `data/logs.jsonl` cho `event=="request_failed"`, kiểm tra `error_type` (thường là `RuntimeError` do vector store timeout).
  3. Mở trace có cùng `correlation_id`, kiểm tra span `retrieval` có status `ERROR` hay `OK`.
- **Mitigation tạm thời:**
  - Nếu là do practice scenario: tắt `tool_fail`: `python scripts/inject_incident.py --scenario tool_fail --disable`.
  - Trong production: kiểm tra trạng thái vector store (latency, error rate, quota). Restart nếu cần. Tạm thời trả lời bằng "tôi chưa có thông tin này" thay vì để 500.
- **Owner:** `student-<MSSV>`

## Alert 3: Cost Spike

- **Tên:** `CostSpike`
- **Severity:** `critical`
- **Duration:** `15m`
- **Kênh thông báo:** Slack `#k4-l3b-alerts`
- **SLI/SLO liên quan:** daily cost guardrail `daily_cost_usd_max: 2.5`
- **Điều kiện và thời gian duy trì:** `sum(cost_usd) > 2.5 USD` trong 15 phút
- **Ảnh hưởng tới người dùng:** chi phí tăng đột biến có thể do prompt dài hơn (nhiều input tokens), output dài hơn (nhiều output tokens), hoặc token leak. Người dùng cảm nhận câu trả lời dài hơn bình thường.
- **Ba bước kiểm tra đầu tiên:**
  1. Mở dashboard panel **Cost** và **Tokens**, xác nhận cost tăng do `tokens_in` hay `tokens_out`.
  2. Lọc `data/logs.jsonl` cho `event=="response_sent"` trong khoảng đó, sắp xếp theo `tokens_in` hoặc `cost_usd` giảm dần, lấy `correlation_id` của request đắt nhất.
  3. Mở trace cùng `correlation_id`, kiểm tra:
     - Metadata `prompt_version` đang dùng version nào (so với baseline).
     - Span `generation` có `usage_details.total` tăng bất thường.
     - Có gắn `prompt_source=langfuse` hay `local-fallback` (nếu fallback → cost do local template, ít khả năng tăng vọt).
- **Mitigation tạm thời:**
  - Nếu do prompt mới (`prompt_version` mới hơn baseline, `tokens_in` cao hơn >20%): rollback `production` về version cũ (xem CP2 6.2).
  - Nếu do `cost_spike` practice scenario: `python scripts/inject_incident.py --scenario cost_spike --disable`.
  - Trong production: giảm `max_tokens` của LLM call, giới hạn độ dài input (`max_input_chars`), throttle traffic nếu cần.
- **Owner:** `student-<MSSV>`

---

## Quy trình tổng quát khi alert bắn

1. **Xác nhận alert không phải false positive**: kiểm tra dashboard trong khoảng `duration`, xem có thật sự vượt ngưỡng không.
2. **Mở dashboard panel liên quan** (latency/errors/cost) để xác định khoảng thời gian.
3. **Lọc log** trong khoảng đó, lấy `correlation_id` đại diện.
4. **Mở trace** cùng `correlation_id`, so sánh span.
5. **Kết luận root cause** từ evidence metric + log + trace.
6. **Áp dụng mitigation** từ runbook; nếu cần rollback hoặc tắt scenario, ghi lại thời điểm và lý do.
7. **Viết incident note** trong `submission/REPORT.md` với chuỗi evidence metric → log → trace.
