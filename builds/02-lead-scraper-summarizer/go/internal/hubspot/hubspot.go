// Package hubspot creates a company record for a scored lead, mirroring
// scout.hubspot_upsert.
package hubspot

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/mazomann/projects/builds/02-lead-scraper-summarizer/go/internal/lead"
)

// Endpoint is the CRM v3 companies collection.
var Endpoint = "https://api.hubapi.com/crm/v3/objects/companies"

var httpClient = &http.Client{Timeout: 20 * time.Second}

// Domain strips scheme, path and a leading www. from a URL, as the Python does.
func Domain(rawURL string) string {
	s := rawURL
	if i := strings.Index(s, "//"); i >= 0 {
		s = s[i+2:]
	}
	if i := strings.Index(s, "/"); i >= 0 {
		s = s[:i]
	}
	return strings.TrimPrefix(s, "www.")
}

// CreateCompany posts a company with the score and opener as custom
// properties (lead_fit_score, lead_opener must exist in the portal).
// Returns the new record id.
func CreateCompany(ctx context.Context, token, pageURL string, a lead.Assessment) (string, error) {
	body, err := json.Marshal(map[string]any{"properties": map[string]any{
		"name":           a.Company,
		"domain":         Domain(pageURL),
		"description":    a.Summary,
		"lead_fit_score": a.FitScore,
		"lead_opener":    a.Opener,
	}})
	if err != nil {
		return "", err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, Endpoint, bytes.NewReader(body))
	if err != nil {
		return "", err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Content-Type", "application/json")
	resp, err := httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return "", err
	}
	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		return "", fmt.Errorf("hubspot HTTP %d: %s", resp.StatusCode, strings.TrimSpace(string(raw)))
	}
	var out struct {
		ID string `json:"id"`
	}
	if err := json.Unmarshal(raw, &out); err != nil {
		return "", fmt.Errorf("decode hubspot response: %w", err)
	}
	return out.ID, nil
}
