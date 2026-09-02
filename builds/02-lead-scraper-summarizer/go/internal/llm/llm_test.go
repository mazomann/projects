package llm

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/mazomann/projects/builds/02-lead-scraper-summarizer/go/internal/lead"
	"github.com/mazomann/projects/builds/02-lead-scraper-summarizer/go/internal/page"
)

const canned = `{"company":"Harbor & Pike Law","summary":"Three-attorney family law firm in Fort Myers doing phone intake via a receptionist.","fit_score":9,"fit_reasons":["phone intake","small firm"],"opener":"Saw that your receptionist takes intake details and an attorney calls back within a day.","red_flags":[]}`

func anthropicReply(stop, text string) string {
	b, _ := json.Marshal(map[string]any{
		"id": "msg_test", "type": "message", "role": "assistant", "model": "claude-sonnet-5",
		"stop_reason": stop,
		"content":     []map[string]string{{"type": "text", "text": text}},
		"usage":       map[string]int{"input_tokens": 10, "output_tokens": 10},
	})
	return string(b)
}

func newClient(t *testing.T, h http.HandlerFunc) *Anthropic {
	t.Helper()
	srv := httptest.NewServer(h)
	t.Cleanup(srv.Close)
	c := NewAnthropic("sk-test", "")
	c.BaseURL = srv.URL
	return c
}

func samplePage() page.Page {
	return page.Page{URL: "https://x.test", Title: "Harbor & Pike Law", Headings: []string{"Practice areas"}, Text: "attorney receptionist <b>bold</b>"}
}

func TestAssessParsesStructuredOutput(t *testing.T) {
	var got request
	var hdr http.Header
	c := newClient(t, func(w http.ResponseWriter, r *http.Request) {
		hdr = r.Header.Clone()
		if r.URL.Path != "/v1/messages" || r.Method != http.MethodPost {
			t.Errorf("unexpected %s %s", r.Method, r.URL.Path)
		}
		if err := json.NewDecoder(r.Body).Decode(&got); err != nil {
			t.Errorf("decode request: %v", err)
		}
		w.Header().Set("content-type", "application/json")
		_, _ = w.Write([]byte(anthropicReply("end_turn", canned)))
	})

	a, err := c.Assess(context.Background(), samplePage(), "small law firms that do intake by phone")
	if err != nil {
		t.Fatal(err)
	}
	if a.FitScore != 9 || a.Company != "Harbor & Pike Law" || len(a.FitReasons) != 2 {
		t.Errorf("assessment = %+v", a)
	}

	if hdr.Get("x-api-key") != "sk-test" || hdr.Get("anthropic-version") != APIVersion || hdr.Get("content-type") != "application/json" {
		t.Errorf("headers = %v", hdr)
	}
	if got.Model != DefaultModel || got.MaxTokens != MaxTokens || got.System != System {
		t.Errorf("request = %+v", got)
	}
	if got.OutputConfig.Format.Type != "json_schema" || len(got.OutputConfig.Format.Schema) == 0 {
		t.Errorf("output_config = %+v", got.OutputConfig)
	}
	if len(got.Messages) != 1 || got.Messages[0].Role != "user" {
		t.Fatalf("messages = %+v", got.Messages)
	}
	var payload struct {
		ICP  string    `json:"icp"`
		Page page.Page `json:"page"`
	}
	if err := json.Unmarshal([]byte(got.Messages[0].Content), &payload); err != nil {
		t.Fatalf("user content is not JSON: %v", err)
	}
	if payload.ICP != "small law firms that do intake by phone" || payload.Page.Title != "Harbor & Pike Law" {
		t.Errorf("payload = %+v", payload)
	}
	if !strings.Contains(got.Messages[0].Content, "<b>bold</b>") {
		t.Errorf("HTML characters were escaped: %s", got.Messages[0].Content)
	}
}

func TestAssessSkipsNonTextBlocks(t *testing.T) {
	body, err := json.Marshal(map[string]any{
		"stop_reason": "end_turn",
		"content": []map[string]string{
			{"type": "thinking", "thinking": ""},
			{"type": "text", "text": canned},
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	c := newClient(t, func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write(body)
	})
	a, err := c.Assess(context.Background(), samplePage(), "icp")
	if err != nil || a.FitScore != 9 {
		t.Errorf("a=%+v err=%v", a, err)
	}
}

func TestAssessRefusal(t *testing.T) {
	c := newClient(t, func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(anthropicReply("refusal", "")))
	})
	_, err := c.Assess(context.Background(), samplePage(), "icp")
	if !errors.Is(err, ErrRefusal) {
		t.Fatalf("err = %v, want ErrRefusal", err)
	}
}

func TestAssessAPIError(t *testing.T) {
	c := newClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		_, _ = w.Write([]byte(`{"type":"error","error":{"type":"authentication_error","message":"invalid x-api-key"}}`))
	})
	_, err := c.Assess(context.Background(), samplePage(), "icp")
	if err == nil || !strings.Contains(err.Error(), "401") || !strings.Contains(err.Error(), "invalid x-api-key") {
		t.Fatalf("err = %v", err)
	}
}

func TestAssessRejectsInvalidAssessment(t *testing.T) {
	bad := strings.Replace(canned, `"fit_score":9`, `"fit_score":11`, 1)
	c := newClient(t, func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(anthropicReply("end_turn", bad)))
	})
	_, err := c.Assess(context.Background(), samplePage(), "icp")
	if err == nil || !strings.Contains(err.Error(), "fit_score") {
		t.Fatalf("err = %v", err)
	}
}

func TestAssessRequiresKey(t *testing.T) {
	c := NewAnthropic("", "")
	if _, err := c.Assess(context.Background(), samplePage(), "icp"); err == nil {
		t.Fatal("expected error without API key")
	}
}

// fake shows the Client interface is satisfiable by a test double, as main
// depends on the interface rather than *Anthropic.
type fake struct{ a lead.Assessment }

func (f fake) Assess(context.Context, page.Page, string) (lead.Assessment, error) { return f.a, nil }

func TestFakeClientSatisfiesInterface(t *testing.T) {
	var c Client = fake{a: lead.Assessment{Company: "x", FitScore: 2, Opener: "y"}}
	a, err := c.Assess(context.Background(), page.Page{}, "icp")
	if err != nil || a.FitScore != 2 {
		t.Fatalf("a=%+v err=%v", a, err)
	}
}
