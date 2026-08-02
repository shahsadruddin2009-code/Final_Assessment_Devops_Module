// Package store defines the persistence abstraction used by the HTTP handlers,
// so the same handler code can run against the in-memory data package (used
// by default and in unit tests) or a real PostgreSQL database (used when
// DATABASE_URL is set, mirroring the Python service's approach).
package store

import "northwind-delivery/pkg/data"

// Store is implemented by every supported delivery backend.
type Store interface {
	All() []data.Delivery
	Find(id string) (data.Delivery, error)
	FilterByStatus(status data.Status) []data.Delivery
	CountByStatus() map[data.Status]int
}

type memoryStore struct{}

// NewMemoryStore returns a Store backed by the process's in-memory data package.
func NewMemoryStore() Store { return memoryStore{} }

func (memoryStore) All() []data.Delivery { return data.All() }

func (memoryStore) Find(id string) (data.Delivery, error) { return data.Find(id) }

func (memoryStore) FilterByStatus(status data.Status) []data.Delivery {
	return data.FilterByStatus(status)
}

func (memoryStore) CountByStatus() map[data.Status]int { return data.CountByStatus() }
