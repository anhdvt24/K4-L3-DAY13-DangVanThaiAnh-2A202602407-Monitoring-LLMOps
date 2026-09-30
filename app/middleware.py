from __future__ import annotations

import re
import secrets
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

# Chỉ chấp nhận header hợp lệ để tránh log injection: chữ, số, '-', '_', độ dài <= 128
_VALID_REQ_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _new_correlation_id() -> str:
    return f"req-{secrets.token_hex(8)}"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Xóa context cũ để tránh rò dữ liệu giữa các request (đặc biệt khi --reload hoặc concurrency > 1)
        clear_contextvars()

        # 2. Lấy correlation ID từ header nếu client gửi, không hợp lệ thì sinh mới
        incoming = request.headers.get("x-request-id")
        correlation_id = incoming if incoming and _VALID_REQ_ID.match(incoming) else _new_correlation_id()

        # 3. Bind vào structlog context để mọi log sau đều có sẵn correlation_id
        bind_contextvars(correlation_id=correlation_id)

        # 4. Cho các layer khác (agent, trace) truy cập qua request.state
        request.state.correlation_id = correlation_id

        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        # 5. Trả lại correlation ID và processing time qua response header
        response.headers["x-request-id"] = correlation_id
        response.headers["x-response-time-ms"] = str(elapsed_ms)
        return response
