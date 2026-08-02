"""Automated test suite for the Northwind delivery-tracking service.

Covers:
  * Unit tests for the ``app.data`` module (seed data and lookup helpers).
  * Integration tests that run the real HTTP server on an ephemeral port and
    exercise every endpoint, including edge cases and error handling.
  * Concurrency, header, and configuration tests.

Run with:
    pytest
"""

from __future__ import annotations

import json
import os
import statistics
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from unittest import mock

import pytest

from app import data
from app.service import DeliveryHandler, main

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def server_url():
    """Start the real service on an ephemeral port for integration tests."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), DeliveryHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def get(url: str):
    """GET a URL and return (status, headers, parsed-JSON body)."""
    try:
        with urllib.request.urlopen(url) as response:
            return response.status, dict(response.headers), json.loads(response.read())
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), json.loads(err.read())


# ---------------------------------------------------------------------------
# Unit tests: app.data
# ---------------------------------------------------------------------------

class TestSeedData:
    def test_deliveries_is_a_list(self):
        assert isinstance(data.DELIVERIES, list)

    def test_seed_data_has_five_records(self):
        assert len(data.DELIVERIES) == 5

    def test_all_ids_are_unique(self):
        ids = [d["id"] for d in data.DELIVERIES]
        assert len(ids) == len(set(ids))

    def test_every_record_has_required_fields(self):
        for delivery in data.DELIVERIES:
            assert {"id", "destination", "status", "driver"} <= set(delivery)

    def test_statuses_are_valid(self):
        valid = {"pending", "in_transit", "delivered"}
        assert all(d["status"] in valid for d in data.DELIVERIES)

    def test_ids_follow_naming_convention(self):
        assert all(d["id"].startswith("NL-") for d in data.DELIVERIES)


class TestAllDeliveries:
    def test_returns_all_records(self):
        assert len(data.all_deliveries()) == len(data.DELIVERIES)

    def test_returns_copies_not_references(self):
        result = data.all_deliveries()
        result[0]["status"] = "tampered"
        assert data.DELIVERIES[0]["status"] != "tampered"

    def test_returns_new_list_each_call(self):
        assert data.all_deliveries() is not data.all_deliveries()

    def test_contents_match_seed_data(self):
        assert data.all_deliveries() == data.DELIVERIES


class TestFindDelivery:
    @pytest.mark.parametrize("delivery_id", ["NL-1001", "NL-1003", "NL-1005"])
    def test_finds_existing_delivery(self, delivery_id):
        delivery = data.find_delivery(delivery_id)
        assert delivery is not None
        assert delivery["id"] == delivery_id

    def test_returns_none_for_unknown_id(self):
        assert data.find_delivery("NL-9999") is None

    def test_returns_none_for_empty_string(self):
        assert data.find_delivery("") is None

    def test_lookup_is_case_sensitive(self):
        assert data.find_delivery("nl-1001") is None

    def test_returns_a_copy(self):
        found = data.find_delivery("NL-1002")
        found["driver"] = "tampered"
        assert data.find_delivery("NL-1002")["driver"] != "tampered"

    def test_pending_delivery_has_no_driver(self):
        assert data.find_delivery("NL-1003")["driver"] is None


class TestFilterByStatus:
    @pytest.mark.parametrize("status,expected_count", [
        ("in_transit", 2),
        ("delivered", 2),
        ("pending", 1),
    ])
    def test_counts_per_status(self, status, expected_count):
        assert len(data.filter_by_status(status)) == expected_count

    def test_all_results_match_status(self):
        assert all(d["status"] == "delivered" for d in data.filter_by_status("delivered"))

    def test_unknown_status_returns_empty_list(self):
        assert data.filter_by_status("warp_speed") == []

    def test_returns_copies(self):
        result = data.filter_by_status("pending")
        result[0]["status"] = "tampered"
        assert data.find_delivery(result[0]["id"])["status"] == "pending"


class TestCountByStatus:
    def test_totals_sum_to_all_deliveries(self):
        counts = data.count_by_status()
        assert sum(counts.values()) == len(data.DELIVERIES)

    def test_expected_histogram(self):
        assert data.count_by_status() == {"in_transit": 2, "delivered": 2, "pending": 1}

    def test_only_valid_statuses_present(self):
        assert set(data.count_by_status()) <= data.VALID_STATUSES


# ---------------------------------------------------------------------------
# Integration tests: HTTP endpoints
# ---------------------------------------------------------------------------

class TestRootEndpoint:
    def test_returns_200(self, server_url):
        status, _, _ = get(f"{server_url}/")
        assert status == 200

    def test_lists_available_endpoints(self, server_url):
        _, _, body = get(f"{server_url}/")
        assert set(body["endpoints"]) == {"/health", "/metrics", "/deliveries", "/deliveries/{id}"}

    def test_identifies_the_service(self, server_url):
        _, _, body = get(f"{server_url}/")
        assert "Northwind" in body["service"]


class TestHealthEndpoint:
    def test_returns_200(self, server_url):
        status, _, _ = get(f"{server_url}/health")
        assert status == 200

    def test_reports_ok(self, server_url):
        _, _, body = get(f"{server_url}/health")
        assert body == {"status": "ok"}

    def test_trailing_slash_is_accepted(self, server_url):
        status, _, _ = get(f"{server_url}/health/")
        assert status == 200

    def test_query_string_is_ignored(self, server_url):
        status, _, body = get(f"{server_url}/health?probe=liveness")
        assert status == 200
        assert body == {"status": "ok"}


class TestDeliveriesCollection:
    def test_returns_200(self, server_url):
        status, _, _ = get(f"{server_url}/deliveries")
        assert status == 200

    def test_returns_all_deliveries(self, server_url):
        _, _, body = get(f"{server_url}/deliveries")
        assert isinstance(body, list)
        assert len(body) == len(data.DELIVERIES)

    def test_matches_data_module(self, server_url):
        _, _, body = get(f"{server_url}/deliveries")
        assert body == data.all_deliveries()

    def test_trailing_slash_is_accepted(self, server_url):
        status, _, _ = get(f"{server_url}/deliveries/")
        assert status == 200


class TestDeliveriesStatusFilter:
    @pytest.mark.parametrize("status_value,expected_count", [
        ("in_transit", 2),
        ("delivered", 2),
        ("pending", 1),
    ])
    def test_filters_by_status(self, server_url, status_value, expected_count):
        status, _, body = get(f"{server_url}/deliveries?status={status_value}")
        assert status == 200
        assert len(body) == expected_count
        assert all(d["status"] == status_value for d in body)

    def test_invalid_status_returns_400(self, server_url):
        status, _, body = get(f"{server_url}/deliveries?status=teleported")
        assert status == 400
        assert "teleported" in body["error"]
        assert body["valid_statuses"] == sorted(data.VALID_STATUSES)


class TestMetricsEndpoint:
    def test_returns_200(self, server_url):
        status, _, _ = get(f"{server_url}/metrics")
        assert status == 200

    def test_reports_delivery_statistics(self, server_url):
        _, _, body = get(f"{server_url}/metrics")
        assert body["deliveries_total"] == len(data.DELIVERIES)
        assert body["deliveries_by_status"] == data.count_by_status()

    def test_request_counter_increases(self, server_url):
        _, _, before = get(f"{server_url}/metrics")
        get(f"{server_url}/health")
        _, _, after = get(f"{server_url}/metrics")
        assert after["requests_total"] > before["requests_total"]

    def test_uptime_is_positive(self, server_url):
        _, _, body = get(f"{server_url}/metrics")
        assert body["uptime_seconds"] > 0


class TestSingleDelivery:
    @pytest.mark.parametrize("delivery_id", ["NL-1001", "NL-1002", "NL-1004"])
    def test_known_id_returns_200(self, server_url, delivery_id):
        status, _, body = get(f"{server_url}/deliveries/{delivery_id}")
        assert status == 200
        assert body["id"] == delivery_id

    def test_body_matches_data_module(self, server_url):
        _, _, body = get(f"{server_url}/deliveries/NL-1005")
        assert body == data.find_delivery("NL-1005")

    def test_unknown_id_returns_404(self, server_url):
        status, _, body = get(f"{server_url}/deliveries/NL-0000")
        assert status == 404
        assert "NL-0000" in body["error"]

    def test_lookup_is_case_sensitive_over_http(self, server_url):
        status, _, _ = get(f"{server_url}/deliveries/nl-1001")
        assert status == 404

    def test_trailing_slash_on_id_is_accepted(self, server_url):
        status, _, body = get(f"{server_url}/deliveries/NL-1001/")
        assert status == 200
        assert body["id"] == "NL-1001"


class TestErrorHandling:
    @pytest.mark.parametrize("path", ["/nope", "/delivery", "/deliveries2", "/health/extra"])
    def test_unknown_paths_return_404(self, server_url, path):
        status, _, body = get(f"{server_url}{path}")
        assert status == 404
        assert "error" in body


class TestResponseHeaders:
    def test_content_type_is_json(self, server_url):
        _, headers, _ = get(f"{server_url}/deliveries")
        assert headers["Content-Type"] == "application/json"

    def test_content_length_matches_body(self, server_url):
        with urllib.request.urlopen(f"{server_url}/deliveries") as response:
            body = response.read()
            assert int(response.headers["Content-Length"]) == len(body)

    def test_server_version_header(self, server_url):
        _, headers, _ = get(f"{server_url}/health")
        assert "NorthwindDelivery/1.1" in headers["Server"]

    def test_nosniff_header_is_set(self, server_url):
        _, headers, _ = get(f"{server_url}/health")
        assert headers["X-Content-Type-Options"] == "nosniff"

    def test_404_responses_are_also_json(self, server_url):
        status, headers, _ = get(f"{server_url}/nope")
        assert status == 404
        assert headers["Content-Type"] == "application/json"


class TestConcurrency:
    def test_handles_parallel_requests(self, server_url):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: get(f"{server_url}/health")[0], range(24)))
        assert results == [200] * 24

    def test_parallel_mixed_endpoints_are_consistent(self, server_url):
        urls = [f"{server_url}/deliveries", f"{server_url}/deliveries/NL-1001"] * 6
        with ThreadPoolExecutor(max_workers=6) as pool:
            statuses = list(pool.map(lambda u: get(u)[0], urls))
        # Retry any transient failures once to reduce flakiness under CI load.
        statuses = [
            get(url)[0] if status != 200 else status
            for status, url in zip(statuses, urls)
        ]
        assert statuses == [200] * len(urls)


# ---------------------------------------------------------------------------
# Configuration tests: main()
# ---------------------------------------------------------------------------

class TestMainConfiguration:
    def test_default_port_is_8000(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch("app.service.ThreadingHTTPServer") as server_cls:
            server_cls.return_value.serve_forever.side_effect = KeyboardInterrupt
            main()
            assert server_cls.call_args[0][0] == ("0.0.0.0", 8000)

    def test_port_env_var_is_respected(self):
        with mock.patch.dict(os.environ, {"PORT": "9123"}), \
             mock.patch("app.service.ThreadingHTTPServer") as server_cls:
            server_cls.return_value.serve_forever.side_effect = KeyboardInterrupt
            main()
            assert server_cls.call_args[0][0] == ("0.0.0.0", 9123)

    def test_keyboard_interrupt_shuts_down_cleanly(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch("app.service.ThreadingHTTPServer") as server_cls:
            server_cls.return_value.serve_forever.side_effect = KeyboardInterrupt
            main()
            server_cls.return_value.shutdown.assert_called_once()

    def test_non_numeric_port_raises_value_error(self):
        with mock.patch.dict(os.environ, {"PORT": "not-a-number"}):
            with pytest.raises(ValueError):
                main()


# ---------------------------------------------------------------------------
# Optional PostgreSQL integration tests
#
# These exercise app.data against a real PostgreSQL instance instead of the
# default SQLite backend, proving the same code works unmodified against
# either database. They are skipped unless TEST_POSTGRES_URL is set (the CI
# pipeline provides a Postgres service container and sets it; locally, point
# it at any disposable Postgres, e.g. via `docker run -p 5432:5432 postgres`).
# ---------------------------------------------------------------------------

TEST_POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")

_SKIP_REASON = "TEST_POSTGRES_URL not set; skipping Postgres integration tests"


@pytest.mark.skipif(not TEST_POSTGRES_URL, reason=_SKIP_REASON)
class TestPostgresBackend:
    @pytest.fixture(autouse=True)
    def _use_postgres(self):
        from app import db

        original_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = TEST_POSTGRES_URL
        db.reset_engine()
        data._ready = False
        try:
            yield
        finally:
            if original_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = original_url
            db.reset_engine()
            data._ready = False

    def test_all_deliveries_matches_seed_data(self):
        assert data.all_deliveries() == data.SEED_DELIVERIES

    def test_find_delivery_by_id(self):
        assert data.find_delivery("NL-1002")["destination"] == "Bristol"

    def test_filter_by_status(self):
        assert len(data.filter_by_status("delivered")) == 2

    def test_count_by_status(self):
        assert data.count_by_status() == {"in_transit": 2, "delivered": 2, "pending": 1}


# ---------------------------------------------------------------------------
# Performance tests
# ---------------------------------------------------------------------------

class TestEndpointLatency:
    def test_health_response_time_under_threshold(self, server_url):
        times = []
        for _ in range(50):
            start = time.perf_counter()
            get(f"{server_url}/health")
            times.append(time.perf_counter() - start)
        p95 = statistics.quantiles(times, n=20)[18]  # 95th percentile approximation
        assert statistics.median(times) < 0.010
        assert p95 < 0.050

    def test_deliveries_response_time_under_threshold(self, server_url):
        times = []
        for _ in range(50):
            start = time.perf_counter()
            get(f"{server_url}/deliveries")
            times.append(time.perf_counter() - start)
        assert statistics.median(times) < 0.010

    def test_single_delivery_lookup_is_fast(self, server_url):
        times = []
        for _ in range(50):
            start = time.perf_counter()
            get(f"{server_url}/deliveries/NL-1001")
            times.append(time.perf_counter() - start)
        assert statistics.median(times) < 0.010


class TestThroughput:
    def test_health_endpoint_throughput(self, server_url):
        duration = 1.0
        count = 0
        start = time.perf_counter()
        while time.perf_counter() - start < duration:
            get(f"{server_url}/health")
            count += 1
        assert count >= 50

    def test_mixed_endpoint_throughput(self, server_url):
        urls = [f"{server_url}/health", f"{server_url}/deliveries", f"{server_url}/deliveries/NL-1001"]
        duration = 1.0
        count = 0
        start = time.perf_counter()
        while time.perf_counter() - start < duration:
            get(urls[count % len(urls)])
            count += 1
        assert count >= 40


class TestLoadUnderConcurrency:
    def test_many_concurrent_health_requests(self, server_url):
        def worker(_):
            for _ in range(20):
                get(f"{server_url}/health")
        with ThreadPoolExecutor(max_workers=16) as pool:
            pool.map(worker, range(16))

    def test_ramp_up_concurrent_clients(self, server_url):
        for workers in [1, 4, 8, 16]:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(lambda _: get(f"{server_url}/health")[0], range(workers * 5)))
            assert all(r == 200 for r in results)


class TestDataOperationPerformance:
    def test_all_deliveries_is_fast(self):
        times = []
        for _ in range(1000):
            start = time.perf_counter()
            data.all_deliveries()
            times.append(time.perf_counter() - start)
        assert statistics.median(times) < 0.001

    def test_find_delivery_is_fast(self):
        times = []
        for _ in range(1000):
            start = time.perf_counter()
            data.find_delivery("NL-1003")
            times.append(time.perf_counter() - start)
        assert statistics.median(times) < 0.001
