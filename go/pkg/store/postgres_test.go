package store

import (
	"os"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"northwind-delivery/pkg/data"
)

// TestPostgresStore exercises the Postgres-backed Store against a real
// database, proving the same query logic works unmodified against either
// backend. It is skipped unless TEST_POSTGRES_URL is set (the CI pipeline
// provides a Postgres service container and sets it).
func TestPostgresStore(t *testing.T) {
	dsn := os.Getenv("TEST_POSTGRES_URL")
	if dsn == "" {
		t.Skip("TEST_POSTGRES_URL not set; skipping Postgres integration test")
	}

	s, err := NewPostgresStore(dsn)
	require.NoError(t, err)

	all := s.All()
	assert.GreaterOrEqual(t, len(all), 5)

	d, err := s.Find("NL-1002")
	require.NoError(t, err)
	assert.Equal(t, "Bristol", d.Destination)

	_, err = s.Find("NL-9999")
	assert.Error(t, err)

	inTransit := s.FilterByStatus(data.InTransit)
	for _, d := range inTransit {
		assert.Equal(t, data.InTransit, d.Status)
	}

	counts := s.CountByStatus()
	assert.GreaterOrEqual(t, counts[data.Delivered], 2)
}
