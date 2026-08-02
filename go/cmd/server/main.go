// Package main runs the Go comparison service.
package main

import (
	"context"
	"flag"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"northwind-delivery/pkg/handlers"
	"northwind-delivery/pkg/store"
)

func main() {
	var healthCheck bool
	flag.BoolVar(&healthCheck, "healthcheck", false, "Run a one-shot container health check")
	flag.Parse()

	if healthCheck {
		if err := runHealthCheck(); err != nil {
			os.Exit(1)
		}
		return
	}

	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	port := getenvInt("PORT", 8000)

	backend, err := newStore(logger)
	if err != nil {
		logger.Error("failed to initialise store", slog.Any("error", err))
		os.Exit(1)
	}

	server := &http.Server{
		Addr:         fmt.Sprintf("0.0.0.0:%d", port),
		Handler:      handlers.NewAPIHandlerWithStore(backend),
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	done := make(chan os.Signal, 1)
	signal.Notify(done, os.Interrupt, syscall.SIGTERM)

	go func() {
		logger.Info("Northwind delivery (Go) listening", slog.Int("port", port))
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Error("server error", slog.Any("error", err))
			os.Exit(1)
		}
	}()

	<-done
	logger.Info("shutting down gracefully")

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := server.Shutdown(ctx); err != nil {
		logger.Error("shutdown error", slog.Any("error", err))
		os.Exit(1)
	}
}

func runHealthCheck() error {
	client := http.Client{Timeout: 3 * time.Second}
	resp, err := client.Get("http://localhost:8000/health")
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("unexpected status %d", resp.StatusCode)
	}
	return nil
}

// newStore picks the PostgreSQL-backed store when DATABASE_URL is set,
// falling back to the in-memory store (used by default and in tests) so the
// service does not require a database to run locally.
func newStore(logger *slog.Logger) (store.Store, error) {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		logger.Info("DATABASE_URL not set; using in-memory store")
		return store.NewMemoryStore(), nil
	}

	logger.Info("connecting to PostgreSQL store")
	return store.NewPostgresStore(dsn)
}

func getenvInt(key string, defaultValue int) int {
	raw := os.Getenv(key)
	if raw == "" {
		return defaultValue
	}
	v, err := strconv.Atoi(raw)
	if err != nil {
		return defaultValue
	}
	return v
}
