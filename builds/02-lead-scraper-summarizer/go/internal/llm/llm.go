// Package llm asks Claude to assess a reduced homepage against an ICP using
// the Anthropic Messages API with a JSON-schema constrained output. It talks
// to the API directly over net/http so the binary carries no SDK.
package llm

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/mazomann/ai-automation-portfolio/builds/02-lead-scraper-summarizer/go/internal/lead"
	"github.com/mazomann/ai-automation-portfolio/builds/02-lead-scraper-summarizer/go/internal/page"
)

const (
	// DefaultBaseURL is the Anthropic API origin.
	DefaultBaseURL = "https://api.anthropic.com"
	// DefaultModel is used when LEAD_MODEL is unset (same as the Python CLI).
	DefaultModel = "claude-sonnet-5"
	// APIVersion is the anthropic-version header value.
	APIVersion = "2023-06-01"
	// MaxTokens bounds the response; the schema keeps output short anyway.
	MaxTokens = 1024
)

// System is the exact prompt used by scout.py.
const System = "You are a sales researcher. Given the text of a company website and an ideal customer profile (ICP), " +
	"write a 3-line factual summary, score fit 1-10 (10 = textbook ICP match), give up to 4 concrete reasons, " +
	"and write ONE opener sentence that references something specific from their site. " +
	"Never invent facts that are not on the page. If the page is not a company site, score 1 and say why in red_flags."

// ErrRefusal is returned when the model declines to answer (stop_reason "refusal").
var ErrRefusal = errors.New("model refused")

// Client scores a page against an ICP. main uses Anthropic; tests inject fakes.
type Client interface {
	Assess(ctx context.Context, p page.Page, icp string) (lead.Assessment, error)
}

// Anthropic calls the Messages API.
type Anthropic struct {
	APIKey  string
	Model   string
	BaseURL string
	HTTP    *http.Client
}

var _ Client = (*Anthropic)(nil)

// NewAnthropic builds a client with production defaults.
func NewAnthropic(apiKey, model string) *Anthropic {
	if model == "" {
		model = DefaultModel
	}
	return &Anthropic{
		APIKey:  apiKey,
		Model:   model,
		BaseURL: DefaultBaseURL,
		HTTP:    &http.Client{Timeout: 120 * time.Second},
	}
}

type request struct {
	Model        string       `json:"model"`
	MaxTokens    int          `json:"max_tokens"`
	System       string       `json:"system"`
	Messages     []message    `json:"messages"`
	OutputConfig outputConfig `json:"output_config"`
}

type message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type outputConfig struct {
	Format format `json:"format"`
}

type format struct {
	Type   string          `json:"type"`
	Schema json.RawMessage `json:"schema"`
}

type response struct {
	StopReason string `json:"stop_reason"`
	Content    []struct {
		Type string `json:"type"`
		Text string `json:"text"`
	} `json:"content"`
	Error *struct {
		Type    string `json:"type"`
		Message string `json:"message"`
	} `json:"error"`
}

// Assess sends {icp, page} as the user message and parses the structured reply.
func (c *Anthropic) Assess(ctx context.Context, p page.Page, icp string) (lead.Assessment, error) {
	var out lead.Assessment
	if c.APIKey == "" {
		return out, errors.New("ANTHROPIC_API_KEY is not set")
	}
	content, err := marshalNoEscape(map[string]any{"icp": icp, "page": p})
	if err != nil {
		return out, err
	}
	body, err := json.Marshal(request{
		Model:        c.Model,
		MaxTokens:    MaxTokens,
		System:       System,
		Messages:     []message{{Role: "user", Content: content}},
		OutputConfig: outputConfig{Format: format{Type: "json_schema", Schema: lead.Schema}},
	})
	if err != nil {
		return out, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, strings.TrimRight(c.BaseURL, "/")+"/v1/messages", bytes.NewReader(body))
	if err != nil {
		return out, err
	}
	req.Header.Set("x-api-key", c.APIKey)
	req.Header.Set("anthropic-version", APIVersion)
	req.Header.Set("content-type", "application/json")
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return out, err
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return out, err
	}
	var r response
	if jerr := json.Unmarshal(raw, &r); jerr != nil && resp.StatusCode == http.StatusOK {
		return out, fmt.Errorf("decode response: %w", jerr)
	}
	if resp.StatusCode != http.StatusOK {
		if r.Error != nil {
			return out, fmt.Errorf("anthropic HTTP %d: %s: %s", resp.StatusCode, r.Error.Type, r.Error.Message)
		}
		return out, fmt.Errorf("anthropic HTTP %d: %s", resp.StatusCode, strings.TrimSpace(string(raw)))
	}
	if r.StopReason == "refusal" {
		return out, ErrRefusal
	}
	for _, b := range r.Content {
		if b.Type != "text" {
			continue
		}
		if err := json.Unmarshal([]byte(b.Text), &out); err != nil {
			return out, fmt.Errorf("parse assessment JSON: %w", err)
		}
		if err := out.Validate(); err != nil {
			return out, fmt.Errorf("invalid assessment: %w", err)
		}
		return out, nil
	}
	return out, errors.New("no text block in response")
}

// marshalNoEscape is json.Marshal without HTML escaping, so page text reaches
// the model as written (json.dumps(ensure_ascii=False) equivalent).
func marshalNoEscape(v any) (string, error) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(v); err != nil {
		return "", err
	}
	return strings.TrimRight(buf.String(), "\n"), nil
}
