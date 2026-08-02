package store

import (
	"database/sql"
	"errors"

	_ "github.com/lib/pq"

	"northwind-delivery/pkg/data"
)

type postgresStore struct {
	db *sql.DB
}

// NewPostgresStore opens a connection pool to PostgreSQL, creates the schema
// if it does not exist yet, and seeds it from data.All() when empty. Pulling
// records happens on demand in the query methods below, not into memory.
func NewPostgresStore(dsn string) (Store, error) {
	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return nil, err
	}
	if err := db.Ping(); err != nil {
		return nil, err
	}
	if err := ensureSchema(db); err != nil {
		return nil, err
	}
	return &postgresStore{db: db}, nil
}

func ensureSchema(db *sql.DB) error {
	if _, err := db.Exec(`
		CREATE TABLE IF NOT EXISTS deliveries (
			id TEXT PRIMARY KEY,
			destination TEXT NOT NULL,
			status TEXT NOT NULL,
			driver TEXT
		)
	`); err != nil {
		return err
	}

	var count int
	if err := db.QueryRow(`SELECT COUNT(*) FROM deliveries`).Scan(&count); err != nil {
		return err
	}
	if count > 0 {
		return nil
	}

	for _, d := range data.All() {
		if _, err := db.Exec(
			`INSERT INTO deliveries (id, destination, status, driver) VALUES ($1, $2, $3, $4)`,
			d.ID, d.Destination, string(d.Status), d.Driver,
		); err != nil {
			return err
		}
	}
	return nil
}

func (s *postgresStore) All() []data.Delivery {
	rows, err := s.db.Query(`SELECT id, destination, status, driver FROM deliveries ORDER BY id`)
	if err != nil {
		return nil
	}
	defer rows.Close()
	return scanRows(rows)
}

func (s *postgresStore) Find(id string) (data.Delivery, error) {
	row := s.db.QueryRow(`SELECT id, destination, status, driver FROM deliveries WHERE id = $1`, id)
	d, err := scanInto(row)
	if err != nil {
		return data.Delivery{}, errors.New("delivery not found")
	}
	return d, nil
}

func (s *postgresStore) FilterByStatus(status data.Status) []data.Delivery {
	rows, err := s.db.Query(
		`SELECT id, destination, status, driver FROM deliveries WHERE status = $1 ORDER BY id`,
		string(status),
	)
	if err != nil {
		return nil
	}
	defer rows.Close()
	return scanRows(rows)
}

func (s *postgresStore) CountByStatus() map[data.Status]int {
	counts := make(map[data.Status]int)

	rows, err := s.db.Query(`SELECT status, COUNT(*) FROM deliveries GROUP BY status`)
	if err != nil {
		return counts
	}
	defer rows.Close()

	for rows.Next() {
		var status string
		var count int
		if err := rows.Scan(&status, &count); err == nil {
			counts[data.Status(status)] = count
		}
	}
	if err := rows.Err(); err != nil {
		return counts
	}
	return counts
}

// scanner is satisfied by both *sql.Row and *sql.Rows.
type scanner interface {
	Scan(dest ...any) error
}

func scanInto(s scanner) (data.Delivery, error) {
	var d data.Delivery
	var status string
	var driver sql.NullString

	if err := s.Scan(&d.ID, &d.Destination, &status, &driver); err != nil {
		return data.Delivery{}, err
	}

	d.Status = data.Status(status)
	if driver.Valid {
		value := driver.String
		d.Driver = &value
	}
	return d, nil
}

func scanRows(rows *sql.Rows) []data.Delivery {
	out := []data.Delivery{}
	for rows.Next() {
		d, err := scanInto(rows)
		if err == nil {
			out = append(out, d)
		}
	}
	return out
}
