// Package page fetches a company homepage and reduces it to the text an
// analyst would read: title, meta description, headings, visible copy.
// It mirrors leadscout/page.py.
package page

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"golang.org/x/net/html"
)

const (
	// UserAgent is sent on every fetch so site owners can identify the bot.
	UserAgent = "Mozilla/5.0 (compatible; lead-scout/0.1; +https://github.com/mazomann/projects)"
	// MaxChars caps the visible text sent to the model; keeps token cost flat.
	MaxChars = 6000
	// MaxHeadings caps the number of h1-h3 headings kept.
	MaxHeadings = 20
	// Timeout is the per-request fetch timeout.
	Timeout = 15 * time.Second
	// maxBody bounds how much HTML is read from a response.
	maxBody = 5 << 20
)

// httpClient follows redirects (net/http default) and times out after Timeout.
var httpClient = &http.Client{Timeout: Timeout}

// Page is the reduced homepage. JSON tags match the Python dict keys so the
// payload sent to the model is identical across implementations.
type Page struct {
	URL         string   `json:"url"`
	Title       string   `json:"title"`
	Description string   `json:"description"`
	Headings    []string `json:"headings"`
	Text        string   `json:"text"`
}

// Fetch downloads the HTML at url with a browser-like User-Agent.
// Any 4xx/5xx status is an error.
func Fetch(ctx context.Context, url string) (string, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("User-Agent", UserAgent)
	req.Header.Set("Accept", "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8")
	resp, err := httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("GET %s: HTTP %d", url, resp.StatusCode)
	}
	body, err := io.ReadAll(io.LimitReader(resp.Body, maxBody))
	if err != nil {
		return "", err
	}
	return string(body), nil
}

// Scrape fetches url and reduces it in one step.
func Scrape(ctx context.Context, url string) (Page, error) {
	src, err := Fetch(ctx, url)
	if err != nil {
		return Page{}, err
	}
	p := Reduce(src)
	p.URL = url
	return p, nil
}

// dropped elements are removed wholesale (with their subtree) before any
// text is extracted, matching the Python decompose() list.
var dropped = map[string]bool{
	"script": true, "style": true, "noscript": true, "svg": true,
	"nav": true, "footer": true, "iframe": true,
}

// Reduce turns raw HTML into a Page (URL left empty).
func Reduce(src string) Page {
	p := Page{Headings: []string{}}
	doc, _ := html.Parse(strings.NewReader(src)) // only fails on reader errors; strings.Reader has none
	var texts []string
	var metaName, metaOG string

	var walk func(n *html.Node)
	walk = func(n *html.Node) {
		switch n.Type {
		case html.ElementNode:
			if dropped[n.Data] {
				return
			}
			switch n.Data {
			case "title":
				if p.Title == "" {
					p.Title = collapse(textOf(n))
				}
			case "meta":
				content := strings.TrimSpace(attr(n, "content"))
				if metaName == "" && attr(n, "name") == "description" {
					metaName = content
				}
				if metaOG == "" && attr(n, "property") == "og:description" {
					metaOG = content
				}
			case "h1", "h2", "h3":
				if len(p.Headings) < MaxHeadings {
					p.Headings = append(p.Headings, collapse(textOf(n)))
				}
			}
		case html.TextNode:
			if t := collapse(n.Data); t != "" {
				texts = append(texts, t)
			}
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			walk(c)
		}
	}
	walk(doc)

	p.Description = metaName
	if p.Description == "" {
		p.Description = metaOG
	}
	p.Text = truncate(strings.Join(texts, " "), MaxChars)
	return p
}

// textOf concatenates the text nodes under n, skipping dropped subtrees.
func textOf(n *html.Node) string {
	var b strings.Builder
	var walk func(*html.Node)
	walk = func(n *html.Node) {
		if n.Type == html.ElementNode && dropped[n.Data] {
			return
		}
		if n.Type == html.TextNode {
			b.WriteString(n.Data)
			b.WriteByte(' ')
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			walk(c)
		}
	}
	walk(n)
	return b.String()
}

func attr(n *html.Node, key string) string {
	for _, a := range n.Attr {
		if strings.EqualFold(a.Key, key) {
			return a.Val
		}
	}
	return ""
}

// collapse trims and squeezes all whitespace runs to a single space.
func collapse(s string) string {
	return strings.Join(strings.Fields(s), " ")
}

// truncate cuts s to at most n runes (Python slices by character).
func truncate(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n])
}
