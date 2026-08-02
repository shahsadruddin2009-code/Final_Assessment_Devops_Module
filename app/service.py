"""A minimal delivery-tracking web service for Northwind Logistics.

It is built on the Python standard library only, so it can be containerised
and deployed without pinning a web framework. It exposes:

    GET /                       service information
    GET /health                 health check, always returns HTTP 200
    GET /metrics                request counters and delivery statistics
    GET /deliveries             all deliveries, as JSON
    GET /deliveries?status=X    deliveries filtered by status
    GET /deliveries/{id}        one delivery as JSON, or HTTP 404 if unknown

The ``/health`` endpoint is deliberately simple and dependency-free so it can
back a container health check and Kubernetes readiness and liveness probes.
``/metrics`` exposes lightweight operational counters for dashboards.

The listening port is read from the ``PORT`` environment variable and defaults
to 8000. The service binds to 0.0.0.0 so it is reachable from outside a
container. On SIGTERM (sent by Kubernetes during pod termination) the server
shuts down gracefully so in-flight requests complete.

Run it locally with:
    python -m app
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from app import data

DELIVERIES_PREFIX = "/deliveries/"

logger = logging.getLogger("northwind")


class Metrics:
    """Thread-safe in-process request counters."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = time.monotonic()
        self._requests_total = 0
        self._responses_by_status: dict[int, int] = {}

    def record(self, status: int) -> None:
        with self._lock:
            self._requests_total += 1
            self._responses_by_status[status] = self._responses_by_status.get(status, 0) + 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "uptime_seconds": round(time.monotonic() - self._started, 3),
                "requests_total": self._requests_total,
                "responses_by_status": {str(k): v for k, v in sorted(self._responses_by_status.items())},
                "deliveries_total": len(data.DELIVERIES),
                "deliveries_by_status": data.count_by_status(),
            }


METRICS = Metrics()


class DeliveryHandler(BaseHTTPRequestHandler):
    """Handle GET requests for the delivery-tracking endpoints."""

    server_version = "NorthwindDelivery/1.1"

    def _send_json(self, status: int, payload: dict | list) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)
        METRICS.record(status)
        self._log_access(status, len(body))

    def _log_access(self, status: int, size: int) -> None:
        logger.info(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "method": self.command,
                    "path": self.path,
                    "status": status,
                    "bytes": size,
                    "client": self.client_address[0],
                }
            )
        )

    def do_GET(self) -> None:  # noqa: N802 - name fixed by http.server
        parsed = urlparse(self.path)
        path = parsed.path
        if len(path) > 1:
            path = path.rstrip("/")

        if path == "/":
            self._send_json(200, {
                "service": "Northwind Logistics delivery tracking",
                "version": self.server_version,
                "endpoints": ["/health", "/metrics", "/deliveries", "/deliveries/{id}"],
            })
        elif path == "/health":
            self._send_json(200, {"status": "ok"})
        elif path == "/metrics":
            self._send_json(200, METRICS.snapshot())
        elif path == "/deliveries":
            self._handle_deliveries(parsed.query)
        elif path.startswith(DELIVERIES_PREFIX):
            delivery_id = path[len(DELIVERIES_PREFIX):]
            delivery = data.find_delivery(delivery_id)
            if delivery is None:
                self._send_json(404, {"error": f"No delivery with id {delivery_id}"})
            else:
                self._send_json(200, delivery)
        else:
            self._send_json(404, {"error": "Not found"})

    def _handle_deliveries(self, query: str) -> None:
        params = parse_qs(query)
        statuses = params.get("status")
        if not statuses:
            self._send_json(200, data.all_deliveries())
            return

        status = statuses[0]
        if status not in data.VALID_STATUSES:
            self._send_json(400, {
                "error": f"Invalid status {status!r}",
                "valid_statuses": sorted(data.VALID_STATUSES),
            })
            return
        self._send_json(200, data.filter_by_status(status))

    def log_message(self, *args) -> None:  # noqa: D401 - silence default logging
        """Suppress the default per-request logging; JSON access logs are used."""
        return


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), DeliveryHandler)

    def handle_sigterm(signum, frame) -> None:
        # Kubernetes sends SIGTERM before killing the pod; shut down cleanly.
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, handle_sigterm)

    print(f"Northwind delivery tracking listening on port {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    finally:
        server.server_close()
        print("Northwind delivery tracking stopped")
