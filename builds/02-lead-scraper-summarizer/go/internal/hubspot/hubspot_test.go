package hubspot

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/mazomann/projects/builds/02-lead-scraper-summarizer/go/internal/lead"
)

func TestDomain(t *testing.T) {
	cases := map[string]string{
		"https://www.example.com/about":  "example.com",
		"http://example.com":             "example.com",
		"example.com/x":                  "example.com",
		"https://shop.example.co.uk/a/b": "shop.example.co.uk",
	}
	for in, want := range cases {
		if got := Domain(in); got != want {
			t.Errorf("Domain(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestCreateCompany(t *testing.T) {
	var got map[string]map[string]any
	var auth string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		auth = r.Header.Get("Authorization")
		_ = json.NewDecoder(r.Body).Decode(&got)
		w.WriteHeader(http.StatusCreated)
		_, _ = w.Write([]byte(`{"id":"4242"}`))
	}))
	defer srv.Close()
	old := Endpoint
	Endpoint = srv.URL
	defer func() { Endpoint = old }()

	a := lead.Assessment{Company: "Harbor & Pike Law", Summary: "s", FitScore: 9, Opener: "o"}
	id, err := CreateCompany(context.Background(), "pat-x", "https://www.harborpike.test/", a)
	if err != nil || id != "4242" {
		t.Fatalf("id=%q err=%v", id, err)
	}
	if auth != "Bearer pat-x" {
		t.Errorf("auth = %q", auth)
	}
	p := got["properties"]
	if p["name"] != "Harbor & Pike Law" || p["domain"] != "harborpike.test" || p["lead_fit_score"] != float64(9) || p["lead_opener"] != "o" {
		t.Errorf("properties = %v", p)
	}
}
