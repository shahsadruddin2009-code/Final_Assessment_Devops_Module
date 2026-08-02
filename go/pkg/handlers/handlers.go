// Package handlers implements the HTTP API for the Go comparison service.
package handlers

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"

	"northwind-delivery/pkg/data"
	"northwind-delivery/pkg/store"
)

var logger = slog.New(slog.NewJSONHandler(os.Stdout, nil))

// Info describes the service and its endpoints.
type Info struct {
	Service   string   `json:"service"`
	Endpoints []string `json:"endpoints"`
	Language  string   `json:"language"`
	Version   string   `json:"version"`
}

// APIHandler is the root HTTP handler.
type APIHandler struct {
	Version string
	Started time.Time
	store   store.Store
	stats   *Metrics
}

// NewAPIHandler creates a handler backed by the in-memory data package.
func NewAPIHandler() *APIHandler {
	return NewAPIHandlerWithStore(store.NewMemoryStore())
}

// NewAPIHandlerWithStore creates a handler backed by the given Store, e.g. a
// PostgreSQL-backed store when DATABASE_URL is configured.
func NewAPIHandlerWithStore(s store.Store) *APIHandler {
	return &APIHandler{
		Version: "2.0.0-go",
		Started: time.Now().UTC(),
		store:   s,
		stats:   NewMetrics(),
	}
}

// statusRecorder captures the status code written by a handler so it can be
// logged and counted after the response has been sent.
type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (r *statusRecorder) WriteHeader(status int) {
	r.status = status
	r.ResponseWriter.WriteHeader(status)
}

func (h *APIHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	start := time.Now()

	requestID := r.Header.Get("X-Request-Id")
	if requestID == "" {
		requestID = uuid.New().String()
	}
	w.Header().Set("X-Request-Id", requestID)

	rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}

	path := strings.TrimRight(r.URL.Path, "/")
	if path == "" {
		path = "/"
	}

	switch {
	case path == "/":
		h.root(rec, r)
	case path == "/health":
		h.health(rec, r)
	case path == "/metrics":
		h.metrics(rec, r)
	case path == "/deliveries":
		h.list(rec, r)
	case strings.HasPrefix(path, "/deliveries/"):
		h.get(rec, r, path[len("/deliveries/"):])
	default:
		respondError(rec, http.StatusNotFound, "Not found")
	}

	h.stats.Record(rec.status)
	logger.Info("request",
		slog.String("request_id", requestID),
		slog.String("method", r.Method),
		slog.String("path", r.URL.Path),
		slog.Int("status", rec.status),
		slog.Float64("duration_ms", float64(time.Since(start).Microseconds())/1000.0),
	)
}

func (h *APIHandler) root(w http.ResponseWriter, _ *http.Request) {
	respondJSON(w, http.StatusOK, Info{
		Service: "Northwind Logistics delivery tracking (Go comparison)",
		Endpoints: []string{
			"/health",
			"/metrics",
			"/deliveries",
			"/deliveries?status=X&sort=id|destination|status&limit=N&offset=N",
			"/deliveries/{id}",
		},
		Language: "Go",
		Version:  h.Version,
	})
}

func (h *APIHandler) health(w http.ResponseWriter, _ *http.Request) {
	respondJSON(w, http.StatusOK, map[string]any{
		"status":    "ok",
		"uptime":    time.Since(h.Started).Seconds(),
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *APIHandler) metrics(w http.ResponseWriter, _ *http.Request) {
	snapshot := h.stats.Snapshot()
	snapshot["deliveries_total"] = len(h.store.All())
	snapshot["deliveries_by_status"] = h.store.CountByStatus()
	respondJSON(w, http.StatusOK, snapshot)
}

func (h *APIHandler) list(w http.ResponseWriter, r *http.Request) {
	statusParam := r.URL.Query().Get("status")

	var deliveries []data.Delivery
	if statusParam == "" {
		deliveries = h.store.All()
	} else {
		status := data.Status(statusParam)
		if !data.ValidStatus(status) {
			respondError(w, http.StatusBadRequest, "Invalid status "+statusParam)
			return
		}
		deliveries = h.store.FilterByStatus(status)
	}

	if sortField := r.URL.Query().Get("sort"); sortField != "" {
		if err := sortDeliveries(deliveries, sortField); err != nil {
			respondError(w, http.StatusBadRequest, err.Error())
			return
		}
	}

	page, err := paginate(deliveries, r.URL.Query().Get("limit"), r.URL.Query().Get("offset"))
	if err != nil {
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	respondJSON(w, http.StatusOK, page)
}

func (h *APIHandler) get(w http.ResponseWriter, _ *http.Request, id string) {
	d, err := h.store.Find(id)
	if err != nil {
		respondError(w, http.StatusNotFound, "No delivery with id "+id)
		return
	}
	respondJSON(w, http.StatusOK, d)
}

// sortDeliveries sorts in place by the given field name.
func sortDeliveries(deliveries []data.Delivery, field string) error {
	switch field {
	case "id":
		sort.Slice(deliveries, func(i, j int) bool { return deliveries[i].ID < deliveries[j].ID })
	case "destination":
		sort.Slice(deliveries, func(i, j int) bool { return deliveries[i].Destination < deliveries[j].Destination })
	case "status":
		sort.Slice(deliveries, func(i, j int) bool { return deliveries[i].Status < deliveries[j].Status })
	default:
		return fmt.Errorf("invalid sort field %q (valid: id, destination, status)", field)
	}
	return nil
}

// paginate slices deliveries according to the offset/limit query parameters.
func paginate(deliveries []data.Delivery, limitParam, offsetParam string) ([]data.Delivery, error) {
	offset := 0
	if offsetParam != "" {
		v, err := strconv.Atoi(offsetParam)
		if err != nil || v < 0 {
			return nil, fmt.Errorf("invalid offset %q", offsetParam)
		}
		offset = v
	}
	if offset >= len(deliveries) {
		return []data.Delivery{}, nil
	}

	limit := len(deliveries) - offset
	if limitParam != "" {
		v, err := strconv.Atoi(limitParam)
		if err != nil || v < 0 {
			return nil, fmt.Errorf("invalid limit %q", limitParam)
		}
		if v < limit {
			limit = v
		}
	}

	return deliveries[offset : offset+limit], nil
}

func respondJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func respondError(w http.ResponseWriter, status int, message string) {
	respondJSON(w, status, map[string]string{"error": message})
}
