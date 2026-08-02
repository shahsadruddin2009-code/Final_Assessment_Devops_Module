package data

import "testing"

// Run with: go test ./pkg/data/... -bench=. -benchmem
//
// These benchmarks quantify the Go in-memory store's raw throughput, useful
// as a direct comparison point against the equivalent Python operations in
// tests/test_app.py::TestDataOperationPerformance (which measures wall-clock
// time per call rather than ns/op, but the same relative comparison holds).

func BenchmarkAll(b *testing.B) {
	for i := 0; i < b.N; i++ {
		_ = All()
	}
}

func BenchmarkFind(b *testing.B) {
	for i := 0; i < b.N; i++ {
		_, _ = Find("NL-1003")
	}
}

func BenchmarkFilterByStatus(b *testing.B) {
	for i := 0; i < b.N; i++ {
		_ = FilterByStatus(InTransit)
	}
}

func BenchmarkCountByStatus(b *testing.B) {
	for i := 0; i < b.N; i++ {
		_ = CountByStatus()
	}
}

func BenchmarkCreate(b *testing.B) {
	driver := "Bench Driver"
	for i := 0; i < b.N; i++ {
		Create("Benchmark City", &driver)
	}
}

// BenchmarkParallelFind measures read throughput under concurrent load,
// showcasing goroutine-friendly reads under the RWMutex-protected store.
func BenchmarkParallelFind(b *testing.B) {
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			_, _ = Find("NL-1001")
		}
	})
}

// BenchmarkParallelAll measures read throughput of the full listing under
// concurrent load.
func BenchmarkParallelAll(b *testing.B) {
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			_ = All()
		}
	})
}
