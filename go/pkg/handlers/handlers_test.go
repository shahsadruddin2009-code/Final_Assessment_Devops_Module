package handlers

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
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

func TestHealthEndpoint(t *testing.T) {
	rr := makeRequest(t, "/health")
	assert.Equal(t, http.StatusOK, rr.Code)
	var body map[string]any
	require.NoError(t, json.Unmarshal(rr.Body.Bytes(), &body))
	assert.Equal(t, "ok", body["status"])
}

func TestMetricsEndpoint(t *testing.T) {
	rr := makeRequest(t, "/metrics")
	assert.Equal(t, http.StatusOK, rr.Code)
	var body map[string]any
	require.NoError(t, json.Unmarshal(rr.Body.Bytes(), &body))
	assert.GreaterOrEqual(t, body["deliveries_total"], float64(5))
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

func TestGetDelivery(t *testing.T) {
	rr := makeRequest(t, "/deliveries/NL-1002")
	assert.Equal(t, http.StatusOK, rr.Code)
	var body map[string]any
	require.NoError(t, json.Unmarshal(rr.Body.Bytes(), &body))
	assert.Equal(t, "NL-1002", body["id"])
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
