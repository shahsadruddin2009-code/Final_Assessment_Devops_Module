package handlers

import (
	"strconv"
	"sync"
	"sync/atomic"
	"time"
)

// Metrics tracks request counters without ever taking a mutex on the hot
// path: sync/atomic.Int64 gives lock-free increments, and sync.Map gives a
// concurrent-safe map keyed by status code. This is a deliberate contrast
// with the Python service's Metrics class, which serialises every increment
// behind a threading.Lock.
type Metrics struct {
	requestsTotal atomic.Int64
	byStatus      sync.Map // int -> *atomic.Int64
	started       time.Time
}

// NewMetrics returns a ready-to-use, concurrency-safe Metrics tracker.
func NewMetrics() *Metrics {
	return &Metrics{started: time.Now()}
}

// Record increments the total request count and the count for status.
func (m *Metrics) Record(status int) {
	m.requestsTotal.Add(1)

	counter, _ := m.byStatus.LoadOrStore(status, new(atomic.Int64))
	counter.(*atomic.Int64).Add(1)
}

// Snapshot returns a point-in-time view suitable for JSON serialisation.
func (m *Metrics) Snapshot() map[string]any {
	byStatus := map[string]int64{}
	m.byStatus.Range(func(key, value any) bool {
		byStatus[strconv.Itoa(key.(int))] = value.(*atomic.Int64).Load()
		return true
	})

	return map[string]any{
		"uptime_seconds":      time.Since(m.started).Seconds(),
		"requests_total":      m.requestsTotal.Load(),
		"responses_by_status": byStatus,
	}
}
