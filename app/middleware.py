import time
import uuid
import json
import traceback
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.logger import logger

class RequestResponseLoggingMiddleware(BaseHTTPMiddleware):
    """
    Audit middleware that logs:
    - Every incoming request (Method, Path, Query params, Body payload, Client IP, Correlation ID)
    - Every outgoing response (HTTP Status code, Execution latency in ms)
    - Full traceback for any unhandled exceptions
    """
    async def dispatch(self, request: Request, call_next):
        req_id = f"req-{uuid.uuid4().hex[:8]}"
        start_time = time.perf_counter()

        method = request.method
        path = request.url.path
        query_params = dict(request.query_params)
        client_host = request.client.host if request.client else "unknown"

        # Safely buffer and read body without breaking downstream endpoint parsing
        body_repr = "<empty>"
        try:
            body_bytes = await request.body()
            if body_bytes:
                raw_text = body_bytes.decode("utf-8", errors="replace")
                try:
                    parsed_json = json.loads(raw_text)
                    body_repr = json.dumps(parsed_json, separators=(',', ':'))
                except Exception:
                    body_repr = raw_text[:500]

            # Re-bind receive so FastAPI endpoint body dependency continues to work seamlessly
            async def receive():
                return {"type": "http.request", "body": body_bytes}
            request._receive = receive
        except Exception as e:
            body_repr = f"<Error reading body: {e}>"

        query_repr = json.dumps(query_params, separators=(',', ':')) if query_params else "{}"
        
        logger.info(
            f"[{req_id}] --> INCOMING: {method} {path} | Client: {client_host} | Query: {query_repr} | Body: {body_repr}"
        )

        try:
            response: Response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            logger.info(
                f"[{req_id}] <-- OUTGOING: {method} {path} | Status: {response.status_code} | Duration: {duration_ms:.2f}ms"
            )
            response.headers["X-Request-ID"] = req_id
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            tb_str = traceback.format_exc()
            logger.error(
                f"[{req_id}] xx ERROR: {method} {path} | Duration: {duration_ms:.2f}ms | Exception: {exc}\n{tb_str}"
            )
            raise exc
