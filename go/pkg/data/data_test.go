package data

import (
	"strings"
	"sync"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestAllReturnsFiveSeedRecords(t *testing.T) {
	all := All()
	assert.Len(t, all, 5)
}

func TestAllReturnsCopies(t *testing.T) {
	all := All()
	all[0].Destination = "Timbuktu"
	assert.NotEqual(t, "Timbuktu", All()[0].Destination)
}

func TestFindExisting(t *testing.T) {
	d, err := Find("NL-1001")
	require.NoError(t, err)
	assert.Equal(t, "NL-1001", d.ID)
}

func TestFindMissing(t *testing.T) {
	_, err := Find("NL-9999")
	assert.Error(t, err)
}

func TestFindTableDriven(t *testing.T) {
	cases := []struct {
		name        string
		id          string
		wantErr     bool
		destination string
	}{
		{"manchester", "NL-1001", false, "Manchester"},
		{"bristol", "NL-1002", false, "Bristol"},
		{"leeds", "NL-1003", false, "Leeds"},
		{"glasgow", "NL-1004", false, "Glasgow"},
		{"cardiff", "NL-1005", false, "Cardiff"},
		{"unknown id", "NL-9999", true, ""},
		{"empty id", "", true, ""},
		{"lowercase id is distinct", "nl-1001", true, ""},
		{"trailing whitespace does not match", "NL-1001 ", true, ""},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			d, err := Find(tc.id)
			if tc.wantErr {
				assert.Error(t, err)
				return
			}
			require.NoError(t, err)
			assert.Equal(t, tc.destination, d.Destination)
		})
	}
}

func TestFilterByStatusTableDriven(t *testing.T) {
	cases := []struct {
		status        Status
		minimumCount  int
		expectAllSame bool
	}{
		{Pending, 1, true},
		{InTransit, 2, true},
		{Delivered, 2, true},
		{Cancelled, 0, true},
		{Status("nonexistent"), 0, true},
	}

	for _, tc := range cases {
		t.Run(string(tc.status), func(t *testing.T) {
			results := FilterByStatus(tc.status)
			assert.GreaterOrEqual(t, len(results), tc.minimumCount)
			for _, d := range results {
				assert.Equal(t, tc.status, d.Status)
			}
		})
	}
}

func TestValidStatusTableDriven(t *testing.T) {
	cases := []struct {
		status Status
		want   bool
	}{
		{Pending, true},
		{InTransit, true},
		{Delivered, true},
		{Cancelled, true},
		{Status("in-transit"), false},
		{Status(""), false},
		{Status("DELIVERED"), false},
	}

	for _, tc := range cases {
		t.Run(string(tc.status), func(t *testing.T) {
			assert.Equal(t, tc.want, ValidStatus(tc.status))
		})
	}
}

func TestCreate(t *testing.T) {
	driver := "J. Doe"
	d := Create("Oxford", &driver)
	assert.Equal(t, "Oxford", d.Destination)
	assert.Equal(t, Pending, d.Status)
	assert.Equal(t, &driver, d.Driver)
	assert.True(t, strings.HasPrefix(d.ID, "NL-"))
}

func TestCreateWithNilDriver(t *testing.T) {
	d := Create("Belfast", nil)
	assert.Nil(t, d.Driver)
	assert.Equal(t, "Belfast", d.Destination)
}

func TestCreateGeneratesUniqueIDs(t *testing.T) {
	seen := make(map[string]bool)
	for i := 0; i < 100; i++ {
		d := Create("Stress-test City", nil)
		assert.False(t, seen[d.ID], "duplicate id generated: %s", d.ID)
		seen[d.ID] = true
	}
}

func TestCreatePersistsInAll(t *testing.T) {
	d := Create("Reading", nil)
	found, err := Find(d.ID)
	require.NoError(t, err)
	assert.Equal(t, "Reading", found.Destination)
}

func TestUpdateStatus(t *testing.T) {
	d, err := UpdateStatus("NL-1003", Delivered)
	require.NoError(t, err)
	assert.Equal(t, Delivered, d.Status)

	d, err = Find("NL-1003")
	require.NoError(t, err)
	assert.Equal(t, Delivered, d.Status)
}

func TestUpdateStatusUnknownID(t *testing.T) {
	_, err := UpdateStatus("NL-DOES-NOT-EXIST", Delivered)
	assert.Error(t, err)
}

func TestUpdateStatusTableDriven(t *testing.T) {
	d := Create("Swansea", nil)

	transitions := []Status{InTransit, Delivered, Cancelled, Pending}
	for _, status := range transitions {
		t.Run(string(status), func(t *testing.T) {
			updated, err := UpdateStatus(d.ID, status)
			require.NoError(t, err)
			assert.Equal(t, status, updated.Status)
		})
	}
}

func TestCountByStatus(t *testing.T) {
	counts := CountByStatus()
	assert.GreaterOrEqual(t, counts[Pending], 1)
	assert.GreaterOrEqual(t, counts[Delivered], 2)
}

func TestCountByStatusSumsToAllRecords(t *testing.T) {
	counts := CountByStatus()
	total := 0
	for _, n := range counts {
		total += n
	}
	assert.Equal(t, len(All()), total)
}

func TestCountByStatusReflectsUpdates(t *testing.T) {
	d := Create("Norwich", nil)
	before := CountByStatus()[Delivered]

	_, err := UpdateStatus(d.ID, Delivered)
	require.NoError(t, err)

	after := CountByStatus()[Delivered]
	assert.Equal(t, before+1, after)
}

func TestCloneDriver(t *testing.T) {
	all := All()
	if all[0].Driver != nil {
		*all[0].Driver = "Tampered"
		assert.NotEqual(t, "Tampered", *All()[0].Driver)
	}
}

func TestCloneTrackingIsIndependent(t *testing.T) {
	d, err := Find("NL-1001")
	require.NoError(t, err)
	d.Tracking = append(d.Tracking, Event{Timestamp: "now", Location: "X", Message: "tampered"})

	fresh, err := Find("NL-1001")
	require.NoError(t, err)
	assert.Empty(t, fresh.Tracking)
}

// TestConcurrentCreate exercises Create from many goroutines simultaneously to
// prove the store's mutex protects against lost updates and data races (run
// with `go test -race` to verify no race is detected).
func TestConcurrentCreate(t *testing.T) {
	before := len(All())

	const goroutines = 50
	var wg sync.WaitGroup
	wg.Add(goroutines)
	for i := 0; i < goroutines; i++ {
		go func() {
			defer wg.Done()
			Create("Concurrent City", nil)
		}()
	}
	wg.Wait()

	after := len(All())
	assert.Equal(t, before+goroutines, after)
}

// TestConcurrentUpdateStatus updates distinct records concurrently and checks
// every update lands correctly, demonstrating goroutine-safe read-modify-write.
func TestConcurrentUpdateStatus(t *testing.T) {
	ids := make([]string, 20)
	for i := range ids {
		ids[i] = Create("Batch City", nil).ID
	}

	var wg sync.WaitGroup
	wg.Add(len(ids))
	for _, id := range ids {
		id := id
		go func() {
			defer wg.Done()
			_, err := UpdateStatus(id, Delivered)
			assert.NoError(t, err)
		}()
	}
	wg.Wait()

	for _, id := range ids {
		d, err := Find(id)
		require.NoError(t, err)
		assert.Equal(t, Delivered, d.Status)
	}
}

// TestConcurrentReadsDuringWrites hammers All() with a bounded number of
// concurrent Create calls to confirm readers never observe a torn/partial
// state. The writer goroutine does a fixed amount of work (rather than
// spinning until a stop signal) so the test can't run away: an unbounded
// writer loop can starve readers under sync.RWMutex's writer-preference
// semantics and cause the store to grow without limit.
func TestConcurrentReadsDuringWrites(t *testing.T) {
	const writes = 200

	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		for i := 0; i < writes; i++ {
			Create("Reader-test City", nil)
		}
	}()

	for i := 0; i < 50; i++ {
		all := All()
		for _, d := range all {
			assert.NotEmpty(t, d.ID)
		}
	}
	wg.Wait()
}
