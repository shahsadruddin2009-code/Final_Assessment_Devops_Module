package handlers

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// Run with: go test ./pkg/handlers/... -bench=. -benchmem
//
// These benchmarks drive the handler directly via httptest.NewRecorder (no
// real network I/O), giving a ns/op figure for pure request-handling
// overhead. Compare against tests/test_app.py::TestEndpointLatency, which
// measures the equivalent Python endpoints' wall-clock latency over real
// HTTP — Go's compiled, goroutine-per-request model is expected to show
// materially lower per-request overhead and allocation counts.

func BenchmarkHealthEndpoint(b *testing.B) {
	h := NewAPIHandler()
	req := httptest.NewRequest(http.MethodGet, "/health", nil)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		h.ServeHTTP(httptest.NewRecorder(), req)
	}
}

func BenchmarkDeliveriesEndpoint(b *testing.B) {
	h := NewAPIHandler()
	req := httptest.NewRequest(http.MethodGet, "/deliveries", nil)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		h.ServeHTTP(httptest.NewRecorder(), req)
	}
}

func BenchmarkDeliveriesFilteredEndpoint(b *testing.B) {
	h := NewAPIHandler()
	req := httptest.NewRequest(http.MethodGet, "/deliveries?status=in_transit&sort=id", nil)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		h.ServeHTTP(httptest.NewRecorder(), req)
	}
}

func BenchmarkGetDeliveryEndpoint(b *testing.B) {
	h := NewAPIHandler()
	req := httptest.NewRequest(http.MethodGet, "/deliveries/NL-1001", nil)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		h.ServeHTTP(httptest.NewRecorder(), req)
	}
}

func BenchmarkMetricsEndpoint(b *testing.B) {
	h := NewAPIHandler()
	req := httptest.NewRequest(http.MethodGet, "/metrics", nil)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		h.ServeHTTP(httptest.NewRecorder(), req)
	}
}

// BenchmarkConcurrentHealthEndpoint measures throughput under simulated
// concurrent load using Go's built-in parallel benchmark runner.
func BenchmarkConcurrentHealthEndpoint(b *testing.B) {
	h := NewAPIHandler()

	b.RunParallel(func(pb *testing.PB) {
		req := httptest.NewRequest(http.MethodGet, "/health", nil)
		for pb.Next() {
			h.ServeHTTP(httptest.NewRecorder(), req)
		}
	})
}
