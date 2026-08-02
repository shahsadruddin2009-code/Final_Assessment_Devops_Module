// Package data holds the in-memory delivery records for the Go comparison service.
package data

import (
	"errors"
	"sync"

	"github.com/google/uuid"
)

// Status represents the lifecycle state of a delivery.
type Status string

const (
	Pending   Status = "pending"
	InTransit Status = "in_transit"
	Delivered Status = "delivered"
	Cancelled Status = "cancelled"
)

// Delivery represents a single parcel delivery.
type Delivery struct {
	ID          string  `json:"id"`
	Destination string  `json:"destination"`
	Status      Status  `json:"status"`
	Driver      *string `json:"driver"`
	Tracking    []Event `json:"tracking,omitempty"`
}

// Event is a timestamped scan/update for a delivery.
type Event struct {
	Timestamp string `json:"timestamp"`
	Location  string `json:"location"`
	Message   string `json:"message"`
}

var (
	seed = []Delivery{
		{ID: "NL-1001", Destination: "Manchester", Status: InTransit, Driver: ptr("A. Okafor")},
		{ID: "NL-1002", Destination: "Bristol", Status: Delivered, Driver: ptr("R. Nowak")},
		{ID: "NL-1003", Destination: "Leeds", Status: Pending, Driver: nil},
		{ID: "NL-1004", Destination: "Glasgow", Status: InTransit, Driver: ptr("S. Patel")},
		{ID: "NL-1005", Destination: "Cardiff", Status: Delivered, Driver: ptr("M. Haddad")},
	}

	store      = append([]Delivery(nil), seed...)
	storeMutex sync.RWMutex
)

func ptr(s string) *string { return &s }

// All returns a deep copy of every delivery record.
func All() []Delivery {
	storeMutex.RLock()
	defer storeMutex.RUnlock()

	out := make([]Delivery, len(store))
	for i, d := range store {
		out[i] = clone(d)
	}
	return out
}

// Find returns the delivery with the given id or an error if not found.
func Find(id string) (Delivery, error) {
	storeMutex.RLock()
	defer storeMutex.RUnlock()

	for _, d := range store {
		if d.ID == id {
			return clone(d), nil
		}
	}
	return Delivery{}, errors.New("delivery not found")
}

// Create adds a new delivery to the store and returns its generated id.
func Create(dest string, driver *string) Delivery {
	storeMutex.Lock()
	defer storeMutex.Unlock()

	d := Delivery{
		ID:          "NL-" + uuid.New().String()[:8],
		Destination: dest,
		Status:      Pending,
		Driver:      driver,
	}
	store = append(store, d)
	return clone(d)
}

// UpdateStatus changes the status of an existing delivery.
func UpdateStatus(id string, status Status) (Delivery, error) {
	storeMutex.Lock()
	defer storeMutex.Unlock()

	for i := range store {
		if store[i].ID == id {
			store[i].Status = status
			return clone(store[i]), nil
		}
	}
	return Delivery{}, errors.New("delivery not found")
}

// CountByStatus returns a histogram of deliveries per status.
func CountByStatus() map[Status]int {
	storeMutex.RLock()
	defer storeMutex.RUnlock()

	counts := make(map[Status]int)
	for _, d := range store {
		counts[d.Status]++
	}
	return counts
}

// ValidStatus reports whether s is a recognised delivery status.
func ValidStatus(s Status) bool {
	switch s {
	case Pending, InTransit, Delivered, Cancelled:
		return true
	}
	return false
}

// FilterByStatus returns copies of all deliveries in the given status.
func FilterByStatus(status Status) []Delivery {
	storeMutex.RLock()
	defer storeMutex.RUnlock()

	out := []Delivery{}
	for _, d := range store {
		if d.Status == status {
			out = append(out, clone(d))
		}
	}
	return out
}

func clone(d Delivery) Delivery {
	copy := d
	if d.Driver != nil {
		s := *d.Driver
		copy.Driver = &s
	}
	copy.Tracking = append([]Event(nil), d.Tracking...)
	return copy
}

// DriverNotAssignedAndPending returns copies of pending deliveries with no driver assigned.
func DriverNotAssignedAndPending() []Delivery {
	storeMutex.RLock()
	defer storeMutex.RUnlock()

	out := []Delivery{}
	for _, d := range store {
		if d.Status == Pending && d.Driver == nil {
			out = append(out, clone(d))
		}
	}
	return out
}
