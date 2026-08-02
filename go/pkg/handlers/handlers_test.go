package handlers

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func makeRequest(t *testing.T, path string) *httptest.ResponseRecorder {
	t.Helper()
	h := NewAPIHandler()
	req := httptest.NewRequest(http.MethodGet, path, nil)
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, req)
	return rr
}

func TestRootEndpoint(t *testing.T) {
	rr := makeRequest(t, "/")
	assert.Equal(t, http.StatusOK, rr.Code)
	var body map[string]any
	require.NoError(t, json.Unmarshal(rr.Body.Bytes(), &body))
	assert.Equal(t, "Go", body["language"])
}

func TestRootEndpointListsEndpoints(t *testing.T) {
	rr := makeRequest(t, "/")
	var body map[string]any
	require.NoError(t, json.Unmarshal(rr.Body.Bytes(), &body))
	endpoints, ok := body["endpoints"].([]any)
	require.True(t, ok)
	assert.GreaterOrEqual(t, len(endpoints), 4)
}

func TestHealthEndpoint(t *testing.T) {
	rr := makeRequest(t, "/health")
	assert.Equal(t, http.StatusOK, rr.Code)
	var body map[string]any
	require.NoError(t, json.Unmarshal(rr.Body.Bytes(), &body))
	assert.Equal(t, "ok", body["status"])
}

func TestHealthEndpointHasTimestamp(t *testing.T) {
	rr := makeRequest(t, "/health")
	var body map[string]any
	require.NoError(t, json.Unmarshal(rr.Body.Bytes(), &body))
	assert.NotEmpty(t, body["timestamp"])
}

func TestMetricsEndpoint(t *testing.T) {
	rr := makeRequest(t, "/metrics")
	assert.Equal(t, http.StatusOK, rr.Code)
	var body map[string]any
	require.NoError(t, json.Unmarshal(rr.Body.Bytes(), &body))
	assert.GreaterOrEqual(t, body["deliveries_total"], float64(5))
}

func TestMetricsCountsRequests(t *testing.T) {
	h := NewAPIHandler()

	before := metricsSnapshot(t, h)
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	h.ServeHTTP(httptest.NewRecorder(), req)
	after := metricsSnapshot(t, h)

	assert.Greater(t, after["requests_total"], before["requests_total"])
}

func metricsSnapshot(t *testing.T, h *APIHandler) map[string]float64 {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, "/metrics", nil)
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, req)

	var body map[string]any
	require.NoError(t, json.Unmarshal(rr.Body.Bytes(), &body))

	total, _ := body["requests_total"].(float64)
	return map[string]float64{"requests_total": total}
}

func TestListDeliveries(t *testing.T) {
	rr := makeRequest(t, "/deliveries")
	assert.Equal(t, http.StatusOK, rr.Code)
	var body []map[string]any
	require.NoError(t, json.Unmarshal(rr.Body.Bytes(), &body))
	assert.GreaterOrEqual(t, len(body), 5)
}

func TestListDeliveriesFilteredByStatus(t *testing.T) {
	rr := makeRequest(t, "/deliveries?status=in_transit")
	assert.Equal(t, http.StatusOK, rr.Code)
	var body []map[string]any
	require.NoError(t, json.Unmarshal(rr.Body.Bytes(), &body))
	for _, d := range body {
		assert.Equal(t, "in_transit", d["status"])
	}
}

func TestListDeliveriesInvalidStatus(t *testing.T) {
	rr := makeRequest(t, "/deliveries?status=teleported")
	assert.Equal(t, http.StatusBadRequest, rr.Code)
}

func TestListDeliveriesStatusTableDriven(t *testing.T) {
	cases := []struct {
		status     string
		wantStatus int
	}{
		{"pending", http.StatusOK},
		{"in_transit", http.StatusOK},
		{"delivered", http.StatusOK},
		{"cancelled", http.StatusOK},
		{"", http.StatusOK},
		{"nonsense", http.StatusBadRequest},
		{"PENDING", http.StatusBadRequest},
	}

	for _, tc := range cases {
		t.Run(tc.status, func(t *testing.T) {
			path := "/deliveries"
			if tc.status != "" {
				path += "?status=" + tc.status
			}
			rr := makeRequest(t, path)
			assert.Equal(t, tc.wantStatus, rr.Code)
		})
	}
}

func TestListDeliveriesSorting(t *testing.T) {
	cases := []struct {
		field string
		key   string
	}{
		{"id", "id"},
		{"destination", "destination"},
		{"status", "status"},
	}

	for _, tc := range cases {
		t.Run(tc.field, func(t *testing.T) {
			rr := makeRequest(t, "/deliveries?sort="+tc.field)
			require.Equal(t, http.StatusOK, rr.Code)

			var body []map[string]any
			require.NoError(t, json.Unmarshal(rr.Body.Bytes(), &body))
			require.NotEmpty(t, body)

			for i := 1; i < len(body); i++ {
				prev, _ := body[i-1][tc.key].(string)
				curr, _ := body[i][tc.key].(string)
				assert.LessOrEqual(t, prev, curr)
			}
		})
	}
}

func TestListDeliveriesInvalidSort(t *testing.T) {
	rr := makeRequest(t, "/deliveries?sort=nonsense")
	assert.Equal(t, http.StatusBadRequest, rr.Code)
}

func TestListDeliveriesPagination(t *testing.T) {
	rr := makeRequest(t, "/deliveries?limit=2&offset=1&sort=id")
	assert.Equal(t, http.StatusOK, rr.Code)

	var body []map[string]any
	require.NoError(t, json.Unmarshal(rr.Body.Bytes(), &body))
	assert.Len(t, body, 2)
}

func TestListDeliveriesPaginationBeyondRange(t *testing.T) {
	rr := makeRequest(t, "/deliveries?offset=1000")
	assert.Equal(t, http.StatusOK, rr.Code)

	var body []map[string]any
	require.NoError(t, json.Unmarshal(rr.Body.Bytes(), &body))
	assert.Empty(t, body)
}

func TestListDeliveriesInvalidPaginationParams(t *testing.T) {
	cases := []string{
		"/deliveries?limit=not-a-number",
		"/deliveries?offset=not-a-number",
		"/deliveries?limit=-1",
		"/deliveries?offset=-1",
	}

	for _, path := range cases {
		t.Run(path, func(t *testing.T) {
			rr := makeRequest(t, path)
			assert.Equal(t, http.StatusBadRequest, rr.Code)
		})
	}
}

func TestGetDelivery(t *testing.T) {
	rr := makeRequest(t, "/deliveries/NL-1002")
	assert.Equal(t, http.StatusOK, rr.Code)
	var body map[string]any
	require.NoError(t, json.Unmarshal(rr.Body.Bytes(), &body))
	assert.Equal(t, "NL-1002", body["id"])
}

func TestGetDeliveryTableDriven(t *testing.T) {
	cases := []struct {
		id         string
		wantStatus int
	}{
		{"NL-1001", http.StatusOK},
		{"NL-1002", http.StatusOK},
		{"NL-1003", http.StatusOK},
		{"NL-1004", http.StatusOK},
		{"NL-1005", http.StatusOK},
		{"NL-0000", http.StatusNotFound},
		{"", http.StatusOK}, // trailing slash on /deliveries/ normalises to /deliveries
	}

	for _, tc := range cases {
		t.Run(tc.id, func(t *testing.T) {
			rr := makeRequest(t, "/deliveries/"+tc.id)
			assert.Equal(t, tc.wantStatus, rr.Code)
		})
	}
}

func TestGetDeliveryNotFound(t *testing.T) {
	rr := makeRequest(t, "/deliveries/NL-0000")
	assert.Equal(t, http.StatusNotFound, rr.Code)
}

func TestUnknownPath(t *testing.T) {
	rr := makeRequest(t, "/nope")
	assert.Equal(t, http.StatusNotFound, rr.Code)
}

func TestTrailingSlash(t *testing.T) {
	rr := makeRequest(t, "/health/")
	assert.Equal(t, http.StatusOK, rr.Code)
}

func TestContentTypeJSON(t *testing.T) {
	rr := makeRequest(t, "/health")
	assert.Equal(t, "application/json", rr.Header().Get("Content-Type"))
}

func TestHealthCheckEndpoint(t *testing.T) {
	rr := makeRequest(t, "/health")
	assert.Equal(t, http.StatusOK, rr.Code)
	var body map[string]any
	require.NoError(t, json.Unmarshal(rr.Body.Bytes(), &body))
	assert.Equal(t, "ok", body["status"])
}

func TestRequestIDHeaderIsSet(t *testing.T) {
	rr := makeRequest(t, "/health")
	assert.NotEmpty(t, rr.Header().Get("X-Request-Id"))
}

func TestRequestIDHeaderIsEchoedWhenProvided(t *testing.T) {
	h := NewAPIHandler()
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	req.Header.Set("X-Request-Id", "test-request-id-123")
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, req)

	assert.Equal(t, "test-request-id-123", rr.Header().Get("X-Request-Id"))
}

func TestRequestIDsAreUniquePerRequest(t *testing.T) {
	h := NewAPIHandler()
	seen := make(map[string]bool)

	for i := 0; i < 20; i++ {
		req := httptest.NewRequest(http.MethodGet, "/health", nil)
		rr := httptest.NewRecorder()
		h.ServeHTTP(rr, req)

		id := rr.Header().Get("X-Request-Id")
		assert.False(t, seen[id], "duplicate request id: %s", id)
		seen[id] = true
	}
}

// TestConcurrentRequestsAgainstRealServer exercises the handler behind a real
// net/http server with many concurrent clients, verifying thread safety of
// the handler, store, and metrics under load.
func TestConcurrentRequestsAgainstRealServer(t *testing.T) {
	server := httptest.NewServer(NewAPIHandler())
	defer server.Close()

	const clients = 32
	var wg sync.WaitGroup
	wg.Add(clients)

	for i := 0; i < clients; i++ {
		go func() {
			defer wg.Done()
			resp, err := http.Get(server.URL + "/deliveries")
			require.NoError(t, err)
			defer resp.Body.Close()
			assert.Equal(t, http.StatusOK, resp.StatusCode)
		}()
	}
	wg.Wait()
}

func TestConcurrentMixedEndpoints(t *testing.T) {
	server := httptest.NewServer(NewAPIHandler())
	defer server.Close()

	paths := []string{"/", "/health", "/metrics", "/deliveries", "/deliveries/NL-1001"}

	var wg sync.WaitGroup
	for _, p := range paths {
		for i := 0; i < 8; i++ {
			wg.Add(1)
			go func(path string) {
				defer wg.Done()
				resp, err := http.Get(server.URL + path)
				require.NoError(t, err)
				defer resp.Body.Close()
				assert.Equal(t, http.StatusOK, resp.StatusCode)
			}(p)
		}
	}
	wg.Wait()
}
