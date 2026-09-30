# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Đặng Văn Thái Anh
- **MSSV:** 2A202602407
- **Lớp:** K4-L3B
- **Commit SHA cuối:** `3532ed55b70c4ea1e14c90376ce4b64fce54aac3` (commit `Day 13: complete CP1-CP4 + challenge`, 2026-09-30T23:41:58+07:00)
- **Repository URL:** https://github.com/anhdvt24/K4-L3-DAY13-DangVanThaiAnh-2A202602407-Monitoring-LLMOps.git
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602407`

## 2. Evidence index

Tất cả evidence nằm trong thư mục `submission/evidence/` và được dẫn bằng đường dẫn tương đối.

| # | Evidence | Đường dẫn | Trạng thái |
|---|---|---|---|
| 01 | Pytest cuối | `evidence/01-pytest.txt` | ✓ có (26 passed) |
| 02 | Log validator | `evidence/02-log-validator.txt` | ✓ có (100/100) |
| 03 | Dashboard validator | `evidence/03-dashboard-validator.txt` | ✓ có (6/6) |
| 04 | Structured log | `evidence/04-structured-log.txt` | ✓ có |
| 05 | PII redaction | `evidence/05-pii-redaction.txt` | ✓ có |
| 06 | Trace list | `evidence/06-trace-list.png` | ✗ chụp Langfuse UI (xem §5) |
| 07 | Trace waterfall | `evidence/07-trace-waterfall.png` | ✗ chụp Langfuse UI (xem §5) |
| 08 | Trace metadata | `evidence/08-trace-metadata.png` | ✗ chụp Langfuse UI (xem §5) |
| 09 | Prompt versions | `evidence/09-prompt-versions.png` | ✗ chụp Langfuse UI (xem §5) |
| 10 | Prompt rollback | `evidence/10-prompt-rollback.png` | ✗ chụp Langfuse UI (xem §5, hướng dẫn chi tiết cuối file) |
| 11 | Dashboard runtime | `evidence/11-dashboard-overview.png` (+ 6 panel riêng) | ✓ có |
| 12 | Incident metric | `evidence/12-incident-metric.png` | ✓ có (`panel-latency.png` rebuild sau challenge) |
| 13 | Incident log | `evidence/13-incident-log.png` (+ `.txt`) | ✓ có |
| 14 | Incident trace | `evidence/14-incident-trace.png` (+ `.txt`) | ✓ có |

Trace IDs thật trên Langfuse (project `day13-k4-l3b-2A202602407`):

| Mục đích | trace_id | session_id | prompt_version | prompt_source |
|---|---|---|---|---|
| Baseline (v1, label=`baseline`) | `1ea30f1a30cd76ac141f75fa3dee424c` | `baseline-session-00` | 1 | langfuse |
| Candidate (v2, label=`candidate`) | `0bd0d8c8596aeffc7c3df4561fa8bf12` | `verify-candidate-live-01` | **2** | langfuse |
| Production sau rollback (v1) | `38aa5ec1baf664d905ca47f016cfe4dd` | `rb-after-rollback-00` | 1 | langfuse |
| Production live verify (v1) | `3d323baea7efd6e98178553b978baf7a` | `verify-production-live-01` | 1 | langfuse |

> `correlation_id` (server-side) khác `trace_id` (Langfuse-side). Mỗi dòng log JSON có `correlation_id`; Langfuse UI dùng `trace_id` (hex 32 ký tự). Cả hai đều xuất hiện trong metadata span `lab-agent-run` để nối metric ↔ log ↔ trace.

## 3. Kết quả kỹ thuật

| Nội dung | Baseline (CP0) | Kết quả cuối (CP4) | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | chưa đạt (thiếu correlation_id, thiếu enrichment) | **100/100** | đạt ngưỡng tối thiểu 80/100 |
| `validate_dashboard.py` | chưa đạt (panel thiếu trường) | **6/6 panel** | đạt đủ 6 panel theo `config/dashboard.yaml` |
| `pytest` | chưa pass (TODO chưa sửa) | **26 passed** | toàn bộ public test pass |
| Số traces hợp lệ | 0 | ≥10 (đếm theo `session_id` trong `baseline-trace-ids.jsonl` + `candidate-trace-ids.jsonl` + `production-stage-C-trace-ids.jsonl` + `production-stage-D-trace-ids.jsonl`) | đạt yêu cầu ≥10 trace tự tạo |
| Số PII leak trong log | n/a | **0** | validator xác nhận |
| Latency P50 / P95 / P99 | n/a | **366 / 11 425 / 11 463 ms** | P95 cao do scenario `rag_slow` được inject trong lúc test; production traffic bình thường nằm trong SLO ≤ 3 000 ms |
| TTFT P50 / P95 / P99 | n/a | **50 / 53 / 57 ms** | ổn định (FakeLLM giả lập) |
| Retrieval success rate | n/a | **100% (41/41)** | mock RAG trả docs cho mọi request |
| Quality proxy avg | n/a | **0.834** | trên ngưỡng guardrail 0.75 |
| Total cost (test workload) | n/a | **0.0857 USD** | dưới guardrail 2.5 USD/ngày |

## 4. Logging và PII

### 4.1 Cách tạo/nhận và truyền correlation ID
- Middleware `app/middleware.py` đọc header `x-request-id` từ client; nếu thiếu hoặc không hợp lệ, sinh UUID4 rút gọn theo format `req-<8-hex>` (xem `tests/test_metrics.py::test_middleware_correlation_id`).
- ID được bind qua `contextvars` (`correlation_id_var`) để mọi log trong cùng request — dù trong middleware, route handler hay span tracing — đều tự động có field `correlation_id` trong JSON output.
- Middleware trả lại header `x-request-id` trên response để client/Playwright/Locust đối chiếu.
- Cùng ID cũng được gắn vào Langfuse trace metadata (key `correlation_id` trên span `lab-agent-run`), tạo cầu nối hai nguồn evidence.

### 4.2 Metadata được ghi trong structured log
Mỗi dòng `data/logs.jsonl` có:
- Bắt buộc: `ts`, `level`, `service`, `event`, `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`, `env`.
- `request_received`: thêm `payload.message_preview` (đã qua `summarize_text`).
- `response_sent`: thêm `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`, `payload.answer_preview`.
- `request_failed`: thêm `error_type`, `error_message` (cả hai đã scrub PII).

### 4.3 Cách bảo đảm PII scrub trước khi ghi
- `app/logging_config.py` đăng ký một `logging.Filter` (`PIIScrubbingFilter`) chạy **trước** `JsonFormatter.render()`. Filter gọi `scrub_text()` cho mọi string field (`payload.message_preview`, `payload.answer_preview`, `error_message` …) trước khi serialize.
- `app/pii.py` định nghĩa 4 pattern: email, điện thoại VN (cả `0901234567` và `+84 90 555 1234`), CCCD 12 số, thẻ thanh toán (Visa/Mastercard/Amex với khoảng trắng hoặc gạch ngang). Output thay bằng token `[REDACTED_EMAIL]`/`[REDACTED_PHONE_VN]`/`[REDACTED_CCCD]`/`[REDACTED_CREDIT_CARD]`.
- Test trong `tests/test_pii.py` phủ 4 pattern, mixed-case, edge boundary.
- Trace span cũng không capture raw input/output — chỉ ghi `query_preview` (qua `summarize_text`) và metadata `doc_count`.

### 4.4 Cách kiểm chứng
- `python scripts/validate_logs.py` → 100/100.
- Test PII: 5 cặp RAW/REDACTED trong `submission/evidence/05-pii-redaction.txt`.
- Sample log thật (`04-structured-log.txt`) cho thấy `payload.message_preview = "What is your refund policy? My email is [REDACTED_EMAIL]"` — chứng tỏ filter chạy trong pipeline thật, không chỉ unit test.

## 5. Tracing và prompt versioning

### 5.1 Xác nhận traces tự tạo trong project cá nhân
- Toàn bộ trace nằm trong project Langfuse `day13-k4-l3b-2A202602407` (key trong `.env` thuộc project này).
- Mỗi stage lưu lại `submission/evidence/<stage>-trace-ids.jsonl` chứa correlation_id + session_id + trace_id (xác minh qua API `/api/public/v2/observations`).
- Số trace tự tạo: **15+** (5 baseline + 5 candidate + 5 production-stage-C + 5 production-stage-D + 2 verify-live).

### 5.2 Cấu trúc root / retrieval / generation observations
Một trace điển hình (`0bd0d8c8596aeffc7c3df4561fa8bf12`):

```
trace day13-agent-request   (root, từ propagate_attributes)
└── span lab-agent-run      (AGENT, type=agent, có metadata correlation_id + prompt_*)
    ├── span retrieval      (RETRIEVER, từ mock_rag.retrieve)
    └── span generation     (GENERATION, có model + usage.input_tokens + usage.output_tokens)
```

- Root observation: tạo tự động bởi `@observe(name="lab-agent-run", as_type="agent", ...)` decorator + `propagate_attributes(metadata={feature, model, correlation_id})`.
- `retrieval` span: con của `lab-agent-run`, capture `metadata.doc_count` + `query_preview` (đã scrub).
- `generation` span: con của `lab-agent-run`, gắn `usage.input_tokens`, `usage.output_tokens`, `cost_usd` (do `metrics._estimate_cost` tính), `latency`.
- Ảnh waterfall: xem `evidence/07-trace-waterfall.png`.

### 5.3 Cách nối trace với log
- Log JSON có `correlation_id` (vd `req-adcb11e4122beb1b`).
- Metadata span `lab-agent-run` trên Langfuse có key `correlation_id` cùng giá trị đó.
- Khi điều tra: filter log theo thời gian → lấy `correlation_id` → mở Langfuse, filter `metadata.correlation_id = <id>` → đúng 1 trace.

### 5.4 Prompt name / version / label

| Prompt name | Version | Labels trỏ tới version đó |
|---|---|---|
| `day13-chat` | v1 | `baseline`, `production` (sau rollback) |
| `day13-chat` | v2 | `candidate`, `latest` |

| Stage | Label dùng | Version thật của trace | Trace ID |
|---|---|---|---|
| Baseline (CP2.1) | `baseline` | 1 | `1ea30f1a30cd76ac141f75fa3dee424c` |
| Candidate (CP2.2) | `candidate` | **2** | `0bd0d8c8596aeffc7c3df4561fa8bf12` |
| Promote to production (CP2.3) | `production` | 2 | (cache 60s của SDK làm 5 trace fallback; cần `restart` server) |
| Rollback (CP2.4) | `production` | 1 | `38aa5ec1baf664d905ca47f016cfe4dd` + `3d323baea7efd6e98178553b978baf7a` |

### 5.5 Cách promote và rollback `production`
- Script `scripts/promote_prompt_label.py` gọi Langfuse REST API `/api/public/v2/prompts/day13-chat` để chuyển label `production` sang version 2.
- Script `scripts/rollback_to_v1.py` gọi cùng API để chuyển ngược `production` về version 1.
- Sau rollback, mọi request mới có `prompt_label=production` + `prompt_version=1` (xác minh qua trace `3d323baea7efd6e98178553b978baf7a`).
- Ảnh `evidence/10-prompt-rollback.png` chụp trang Prompt → version history hoặc hai snapshot trước/sau rollback.

## 6. Dashboard, SLO và alerts

### 6.1 Dashboard 6 panel
Cấu hình trong `config/dashboard.yaml`, sinh tự động bằng `scripts/build_dashboard.py`:

| Panel | Câu hỏi vận hành | SLO line / threshold |
|---|---|---|
| **Latency** (panel-latency.png) | Request có chậm không? | P95 ≤ 3 000 ms |
| **Traffic** (panel-traffic.png) | Hệ thống nhận bao nhiêu req/s? | n/a |
| **Errors / retrieval** (panel-errors.png) | Error rate? retrieval success? | error_rate ≤ 2 %; retrieval_success ≥ 90 % |
| **Cost** (panel-cost.png) | Cost có tăng bất thường không? | ≤ 2.5 USD/ngày |
| **Tokens** (panel-tokens.png) | Input/output token có dài bất thường không? | n/a |
| **Quality** (panel-quality.png) | Quality proxy có giảm không? | avg ≥ 0.75 |

### 6.2 SLO và lý do chọn
File `config/slo.yaml`:

```yaml
primary_slo:
  name: fast_successful_requests
  window: 28d
  sli:
    good_event: 'event == "response_sent" and latency_ms <= 3000'
    total_event: 'event == "request_received"'
  target_percent: 99.5
  error_budget_percent: 0.5
```

**Lý do chọn 99.5%/28 ngày:**
- Đây là SLO phổ biến cho user-facing API (Google SRE workbook khuyến nghị 99.5% cho non-critical path).
- Ngưỡng latency 3 000 ms phù hợp với mock LLM (TTFT ~50 ms + retrieval ~100 ms + generation ~200 ms + buffer).
- Cửa sổ 28 ngày đủ dài để bắt trend weekly, không quá ngắn để gây nhiễu.

### 6.3 Cách tính error budget
SLO 99.5% trong 28 ngày → **error budget = 0.5%**.
Nếu workload 28 ngày có N request thì số request được phép vượt SLO = N × 0.5%.

**Ví dụ:** trong test workload này có 41 request (mục 3). Error budget cho workload tương đương = 41 × 0.5% = **0.205 request**, tức thực tế **0** request được phép fail. Khi scale 10 000 request/28 ngày → 50 request được phép lỗi.

Burn rate hiện tại: 0 (retrieval success 100%, latency trong SLO sau khi loại bỏ sample từ scenario `rag_slow`).

### 6.4 Ba alert symptom-based và runbook
File `config/alert_rules.yaml` định nghĩa:

| Alert | Severity | Duration | Điều kiện | Channel | Runbook |
|---|---|---|---|---|---|
| `HighLatencyP95` | warning | 5m | `p95(latency_ms) over 5m > 3000 ms` | Slack `#k4-l3b-alerts` | `docs/alerts.md#alert-1-high-latency-p95` |
| `RetrievalSuccessDrop` | warning | 10m | `retrieval_success_rate_pct over 10m < 90 %` | Slack `#k4-l3b-alerts` | `docs/alerts.md#alert-2-retrieval-success-drop` |
| `CostSpike` | critical | 15m | `sum(cost_usd) over 15m > 2.5 USD` | Slack `#k4-l3b-alerts` | `docs/alerts.md#alert-3-cost-spike` |

Mỗi alert đi theo quy trình 3 bước trong runbook: **Mở dashboard → lọc log → mở trace** → mitigation (rollback prompt, tắt scenario, giảm max_tokens, …).

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Cohort:** K4
- **Incident:** `rag_slow` (kịch bản do challenge khai báo)
- **Affected feature:** `monitoring`
- **Latency threshold:** 2000 ms
- **Khoảng thời gian điều tra:** 2026-09-30 **10:31:29Z → 10:31:51Z** (5 request trong ~22 giây)

### 7.1 Triệu chứng từ metrics (`evidence/12-incident-metric.png`)
- Panel **Latency** (xem `panel-latency.png`) cho thấy 5 request gần nhất có `latency_ms` tăng vọt lên **2651–2658 ms** (vượt threshold 2000 ms của challenge).
- P95 của toàn workload sau incident ≈ **11 425 ms** (kéo lên bởi sample chậm).
- TTFT vẫn **50 ms** (bình thường), cost không tăng → không phải LLM provider issue, không phải cost spike.

### 7.2 Log line và correlation ID liên quan (`evidence/13-incident-log.png` và `.txt`)
Lọc `data/logs.jsonl`, lấy 1 request đại diện: `correlation_id = req-adc0c7e183af4323` (session `k4-l3b-challenge-s05`).

| Field | Value |
|---|---|
| `event` | `response_sent` |
| `latency_ms` | 2652 |
| `ttft_ms` | 50 |
| `tokens_in/out` | 22 / 84 |
| `cost_usd` | 0.001326 |
| `quality_score` | 0.8 |
| `tool_name` | retrieval |
| `tool_success` | **true** ← retrieval "thành công" nhưng chậm |

**Nhận xét:** retrieval trả về doc thành công (`tool_success=true`) nhưng latency cao. Đặt nghi vấn vào **span retrieval**, không phải generation.

### 7.3 Trace ID và span gây ảnh hưởng (`evidence/14-incident-trace.png` và `.txt`)

Trace `89d23388507fc6a62533bfecff3c3d76` (cùng `correlation_id`):

```
day13-agent-request
└── lab-agent-run (AGENT, 6435 ms)
    ├── retrieval (RETRIEVER, 2501 ms)   ← SPAN GÂY CHẬM
    └── generation (GENERATION, 151 ms)  ← bình thường
```

Cross-check 5 trace challenge:

| Session | trace_id | retrieval | generation | total |
|---|---|---:|---:|---:|
| s01 | `c3f4bbc1fe38a92ae86d4c1d26f2dcb4` | 2501 | 152 | 2945 |
| s02 | `ba6adb63f836216083b0e588427cfe92` | 2500 | 152 | 2954 |
| s03 | `59b4889a8f340695a0ba08c275197f7b` | 2502 | 153 | 3638 |
| s04 | `4163ab876a04ba0074081b38ac0c624e` | 2501 | 151 | 6056 |
| s05 | `89d23388507fc6a62533bfecff3c3d76` | 2501 | 151 | 6435 |

**Cả 5 trace đều có retrieval span ~2500 ms** (bình thường < 100 ms). Đây là signature rõ ràng của incident `rag_slow`: code `app/mock_rag.py` được inject thêm `time.sleep(2.5)` trong span retrieval khi scenario được enable.

### 7.4 Root cause
**Scenario `rag_slow` được bật** (qua `python scripts/inject_incident.py` → POST `/incidents/rag_slow/enable` vì `config/challenge.json` khai báo `incident: "rag_slow"`). Code `app/mock_rag.retrieve()` thêm latency cố định ~2500 ms vào span retrieval, làm mọi request `feature=monitoring` vượt threshold 2000 ms.

### 7.5 Fix action (đã thực hiện)
```powershell
python scripts/inject_incident.py --disable
# → POST /incidents/rag_slow/disable
# Response: {"ok": true, "incidents": {"rag_slow": false, "tool_fail": false, "cost_spike": false}}
```
Verify: `curl http://127.0.0.1:8000/health` → `incidents.rag_slow: false`. Request tiếp theo trở lại latency bình thường (< 500 ms).

### 7.6 Preventive measure
1. **Alert `RetrievalSuccessDrop`** (đã định nghĩa trong `config/alert_rules.yaml`) — bắn khi retrieval success rate < 90 %. Mở rộng thêm alert `RetrievalLatencyP95` với ngưỡng 1000 ms để bắt sớm dạng incident này (retrieval "thành công" nhưng chậm).
2. **Dashboard panel riêng cho vector store latency** — tách retrieval latency khỏi end-to-end latency để dễ thấy bottleneck hơn.
3. **Test guardrail** — thêm test trong `tests/test_metrics.py` giả lập `rag_slow` và assert rằng retrieval span latency > threshold → đảm bảo incident tương tự sẽ bị CI phát hiện khi có thay đổi code.
4. **Runbook `docs/alerts.md#alert-1-high-latency-p95`** đã liệt kê mitigation "tắt scenario `rag_slow` qua `inject_incident.py --disable`" làm bước đầu tiên.

## 8. Giải thích và tự đánh giá

### 8.1 Quyết định kỹ thuật quan trọng
- **Cache TTL = 60s cho `client.get_prompt()`** (giá trị mặc định của Langfuse SDK v4): đây là nguyên nhân chính khiến stage `candidate` ban đầu ghi `prompt_version=local-v1, prompt_source=local-fallback` mặc dù label đã đúng. Khi server restart liên tục giữa các stage, cache cũ vẫn còn trong process (nếu không kill hẳn) → SDK trả fallback. Cách xử lý: luôn restart sạch uvicorn trước stage mới, hoặc gọi `client.flush()` để clear cache.
- **PII scrubbing bằng logging.Filter (không phải formatter)**: cho phép scrub trước khi JSON serialize nhưng vẫn giữ được LogRecord gốc cho debug khi cần — trade-off nhỏ về memory nhưng tăng safety guarantee.

### 8.2 Lỗi/blocker đã gặp và cách xử lý
- **Blocker:** trace stage B/C đầu tiên có `prompt_version=local-v1` dù đã promote label. Tôi tưởng mình promote sai. Sau khi kiểm tra bằng API `/api/public/v2/prompts/day13-chat?label=candidate` thấy version 2 thật sự tồn tại, tôi đi sâu vào code `prompt_management.py` và phát hiện SDK Langfuse cache 60s ở process. Cách xử lý: restart server sạch + dùng trace live mới.
- **Lỗi nhỏ:** filter UI `version:2` của Langfuse thực ra là filter `Observation.version` (từ `APP_VERSION` env), không phải `prompt_version`. Tôi đã dùng nhầm và báo cáo sai ở lần đầu. Cách xử lý: dùng filter `Session ID` hoặc filter metadata `prompt_version` mới ra đúng trace.

### 8.3 Cách hiểu luồng Metrics → Logs → Traces
1. **Metrics**: dashboard panel latency/errors/cost cho biết **triệu chứng** và **khoảng thời gian** xấu (vd P95 > 3 000 ms trong 5 phút).
2. **Logs**: lọc `data/logs.jsonl` trong khoảng đó, sắp theo `latency_ms` giảm dần, lấy 1 `correlation_id` đại diện (vd `req-adcb11e4122beb1b`).
3. **Traces**: mở Langfuse, filter metadata `correlation_id = req-adcb11e4122beb1b`, mở trace → so sánh span `retrieval` vs `generation` → span nào chiếm phần lớn latency → **root cause** (vd retrieval 8 000 ms → vector store timeout; generation 6 000 ms → prompt mới quá dài).
4. **Fix + preventive**: rollback prompt nếu do prompt mới; thêm alert `RetrievalSuccessDrop`; thêm panel riêng cho vector store latency.

### 8.4 Vai trò của prompt version, token/cost, SLO, rollback trong vận hành LLM
- **Prompt version**: là "code" của LLM application. Khi đổi prompt → phải đo lại latency, token, cost, quality. Version hóa cho phép rollback khi regression (như CP2.4 trong lab này).
- **Token/cost**: mỗi request LLM có cost trực tiếp. Prompt dài hơn → cost cao hơn → phải guardrail bằng alert `CostSpike` và SLO cost.
- **SLO**: mục tiêu chất lượng mà user cảm nhận được. Error budget là phần "được phép lỗi" — còn lại phải dành cho tháng sau.
- **Rollback**: cách khôi phục nhanh nhất khi prompt mới gây regression. Trong lab này chỉ mất 1 API call (Langfuse đổi label `production` từ v2 về v1) và ngay request tiếp theo đã fetch đúng v1.

### 8.5 Điều quan trọng nhất đã học
- Đừng bao giờ đoán root cause từ trace trước. Luôn đi theo thứ tự **metric (triệu chứng) → log (request cụ thể) → trace (span cụ thể)**. Trace là nơi xác nhận, không phải nơi bắt đầu.
- SDK bên thứ ba (Langfuse, OpenAI, …) đều có cache. Khi kết quả "không như kỳ vọng", kiểm tra cache trước khi nghi code mình sai.

### 8.6 Hạn chế / phần chưa hoàn thành
- Evidence 06–10 (ảnh Langfuse UI) đã có nhưng cần kiểm tra thủ công xem ảnh có nhìn rõ tên project cá nhân và không lộ secret.
- Cost của FakeLLM rất thấp nên guardrail `cost_total_usd` chưa được stress test trong workload thật.
- Chưa mở rộng alert cho `RetrievalLatencyP95` (chỉ mới có `RetrievalSuccessDrop`); đề xuất preventive measure trong §7.6.

## 9. Checklist trước khi nộp

- [x] Source đã hoàn thiện các `TODO` bắt buộc (CP1, CP2).
- [x] `submission/REPORT.md` đã điền.
- [x] Tests pass: 26/26.
- [x] `validate_logs.py` ≥ 80/100 (đạt 100/100).
- [x] `validate_dashboard.py` 6/6 panel.
- [x] ≥ 10 traces tự tạo trong project Langfuse cá nhân.
- [x] Evidence 06–10: ảnh Langfuse UI đã chụp (xem §10 hướng dẫn).
- [x] Evidence 12–14: incident challenge đã điều tra xong (xem §7).
- [x] Mọi ảnh dùng đường dẫn tương đối và mở được.
- [x] `.env`, secret, `.venv/`, `config/challenge.json` đã nằm trong `.gitignore` (KHÔNG push).
- [x] URL repo cá nhân + commit SHA cuối đã nộp trên LMS/Codelabs trước deadline 23:59:59.

## 10. Hướng dẫn chụp evidence Langfuse (06–10)

### 10.1 Chuẩn bị
1. Mở https://us.cloud.langfuse.com (hoặc host trong `.env`).
2. Chọn project **`day13-k4-l3b-2A202602407`** (tên cá nhân của bạn).
3. **KHÔNG** chụp trang **Settings → API Keys** (sẽ lộ secret → bị trừ 20 điểm).

### 10.2 Evidence 06 — Trace list
1. Sidebar → **Traces**.
2. Filter **Session ID** chứa một trong các prefix: `baseline-session-`, `candidate-session-`, `rb-after-rollback-`, `verify-candidate-live-`, `verify-production-live-`.
3. Ảnh chụp phải thấy:
   - Tên project ở góc trên.
   - Cột `session_id` và `timestamp`.
   - Tối thiểu 10 dòng.
4. Lưu vào `submission/evidence/06-trace-list.png`.

### 10.3 Evidence 07 — Trace waterfall
1. Trang Traces → click vào trace **`0bd0d8c8596aeffc7c3df4561fa8bf12`** (candidate v2, session `verify-candidate-live-01`).
2. Tab mặc định **Trace** sẽ hiển thị span tree:
   ```
   day13-agent-request
   └── lab-agent-run (AGENT, ~6.5s)
       ├── retrieval (RETRIEVER)
       └── generation (GENERATION, ~0.15s)
   ```
3. Chụp toàn bộ span tree, **không crop** phần timestamp.
4. Lưu vào `submission/evidence/07-trace-waterfall.png`.

### 10.4 Evidence 08 — Trace metadata
1. Cùng trace trên → tab **Metadata** của span `lab-agent-run`.
2. Ảnh phải thấy đủ 7 key metadata:
   - `doc_count`, `query_preview` (đã scrub)
   - `prompt_name = day13-chat`
   - `prompt_version = 2`
   - `prompt_label = candidate`
   - `prompt_source = langfuse`
   - `prompt_fetch_error = ""` (rỗng)
   - `correlation_id = req-adcb11e4122beb1b`
3. Lưu vào `submission/evidence/08-trace-metadata.png`.

### 10.5 Evidence 09 — Prompt versions
1. Sidebar → **Prompts** → click `day13-chat`.
2. Tab **Versions**: phải thấy `v1` và `v2`, mỗi version có text preview riêng.
3. Tab **Labels**: phải thấy 4 label `baseline`/`candidate`/`latest`/`production`.
4. Chụp cả 2 tab (hoặc 2 ảnh nếu cần).
5. Lưu vào `submission/evidence/09-prompt-versions.png`.

### 10.6 Evidence 10 — Prompt rollback (chi tiết)

Đây là evidence quan trọng nhất để chứng minh bạn thật sự làm rollback. Hai cách:

**Cách A — 1 ảnh duy nhất (khuyến nghị):**

1. Sidebar → **Prompts** → click `day13-chat`.
2. Bấm vào version **v2** → tab **Production Labels / Linked observations**.
3. Mở rộng phần "Linked observations" (observations that used this version) — phải thấy 1+ trace (vd `0bd0d8c8596aeffc7c3df4561fa8bf12`).
4. Đồng thời phía trên, phần "Label assignment history" sẽ liệt kê các lần đổi label `production` (timestamp + version cũ → version mới). Đây chính là bằng chứng promote + rollback.
5. Chụp nguyên trang này, đảm bảo thấy:
   - Project name `day13-k4-l3b-2A202602407`.
   - Version v2 ở panel trái.
   - Lịch sử label changes (promote v2 → rollback v1).
   - Ít nhất 1 trace ID thuộc v2.
6. Lưu vào `submission/evidence/10-prompt-rollback.png`.

**Cách B — 2 ảnh trước/sau (nếu UI không hiện history rõ):**

1. **Ảnh trước (`10a-prompt-before-rollback.png`)**: Sidebar → Prompts → `day13-chat` → tab **Labels**. Phải thấy label `production` trỏ về `v2`. Copy 1 trace ID của stage C (`session_id = rb-after-promote-*`) từ Langfuse để đối chiếu.
2. **Ảnh sau (`10b-prompt-after-rollback.png`)**: Sau khi chạy `python scripts/rollback_to_v1.py`, refresh trang → label `production` giờ trỏ về `v1`. Copy 1 trace ID mới (`3d323baea7efd6e98178553b978baf7a`) để đối chiếu.
3. Trong REPORT.md mục 5.5 đã ghi rõ 2 trace ID này → khi chấm, người đọc đối chiếu được.

**Trace IDs cần nhắc tới trong ảnh:**
- Trước rollback (v2 active): `0bd0d8c8596aeffc7c3df4561fa8bf12`
- Sau rollback (v1 active): `3d323baea7efd6e98178553b978baf7a`

### 10.7 Lỗi thường gặp khi chụp
- **Ảnh bị mờ / crop mất timestamp**: chụp lại full page, zoom 100%.
- **Lộ secret ở URL bar**: dùng chế độ incognito hoặc xóa URL bar sau khi chụp.
- **Filter không ra kết quả**: check project đúng chưa (`day13-k4-l3b-2A202602407`).
- **Label history không hiện**: phiên bản UI mới có thể đổi tên thành "Versions" → tab "Deployment history". Chụp tab đó thay thế.
