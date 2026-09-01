// Package lead defines what the model returns per company, the JSON schema
// that constrains it, validation, and CSV output. It mirrors
// leadscout/schema.py plus the CSV half of scout.py.
package lead

import (
	"encoding/csv"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"sort"
	"strconv"
	"strings"
)

// Assessment is one scored company.
type Assessment struct {
	Company    string   `json:"company"`
	Summary    string   `json:"summary"`
	FitScore   int      `json:"fit_score"`
	FitReasons []string `json:"fit_reasons"`
	Opener     string   `json:"opener"`
	RedFlags   []string `json:"red_flags"`
}

// Schema is the JSON schema passed to the API as output_config.format.schema.
// It is byte-for-byte the same shape as schema.py's JSON_SCHEMA.
var Schema = json.RawMessage(`{
  "type": "object",
  "additionalProperties": false,
  "required": ["company", "summary", "fit_score", "fit_reasons", "opener", "red_flags"],
  "properties": {
    "company": {"type": "string"},
    "summary": {"type": "string"},
    "fit_score": {"type": "integer", "minimum": 1, "maximum": 10},
    "fit_reasons": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
    "opener": {"type": "string"},
    "red_flags": {"type": "array", "items": {"type": "string"}}
  }
}`)

// Validate enforces the invariants the schema cannot fully express.
func (a Assessment) Validate() error {
	var errs []error
	if strings.TrimSpace(a.Company) == "" {
		errs = append(errs, errors.New("company is empty"))
	}
	if strings.TrimSpace(a.Opener) == "" {
		errs = append(errs, errors.New("opener is empty"))
	}
	if a.FitScore < 1 || a.FitScore > 10 {
		errs = append(errs, fmt.Errorf("fit_score %d not in 1..10", a.FitScore))
	}
	if len(a.FitReasons) > 4 {
		errs = append(errs, fmt.Errorf("%d fit_reasons, max 4", len(a.FitReasons)))
	}
	return errors.Join(errs...)
}

// Row is an Assessment tied to the URL it came from, plus the optional
// HubSpot record id created for it.
type Row struct {
	URL       string
	HubSpotID string
	Assessment
}

// Sort orders rows by fit score, highest first, keeping input order for ties.
func Sort(rows []Row) {
	sort.SliceStable(rows, func(i, j int) bool { return rows[i].FitScore > rows[j].FitScore })
}

// WriteCSV sorts rows by score descending and writes them as CSV. The
// hubspot_id column is only emitted when at least one row has an id, which
// matches the Python DictWriter behaviour.
func WriteCSV(w io.Writer, rows []Row) error {
	Sort(rows)
	withHub := false
	for _, r := range rows {
		if r.HubSpotID != "" {
			withHub = true
			break
		}
	}
	header := []string{"url", "company", "summary", "fit_score", "fit_reasons", "opener", "red_flags"}
	if withHub {
		header = append(header, "hubspot_id")
	}
	cw := csv.NewWriter(w)
	if err := cw.Write(header); err != nil {
		return err
	}
	for _, r := range rows {
		rec := []string{
			r.URL, r.Company, r.Summary, strconv.Itoa(r.FitScore),
			strings.Join(r.FitReasons, " | "), r.Opener, strings.Join(r.RedFlags, " | "),
		}
		if withHub {
			rec = append(rec, r.HubSpotID)
		}
		if err := cw.Write(rec); err != nil {
			return err
		}
	}
	cw.Flush()
	return cw.Error()
}
