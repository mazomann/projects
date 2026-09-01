package page

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Fixtures are shared with the Python tests; go test runs with the package
// directory as cwd, so this resolves to <build>/sample-data/fixtures.
const fixtures = "../../../sample-data/fixtures"

func load(t *testing.T, name string) string {
	t.Helper()
	b, err := os.ReadFile(filepath.Join(fixtures, name))
	if err != nil {
		t.Fatalf("read fixture %s: %v", name, err)
	}
	return string(b)
}

func contains(list []string, want string) bool {
	for _, s := range list {
		if s == want {
			return true
		}
	}
	return false
}

func TestReduceStripsChromeAndKeepsSignal(t *testing.T) {
	p := Reduce(load(t, "lawfirm.html"))
	if !strings.HasPrefix(p.Title, "Harbor & Pike Law") {
		t.Errorf("title = %q", p.Title)
	}
	if !strings.Contains(p.Description, "239-555-0100") {
		t.Errorf("description = %q", p.Description)
	}
	if !contains(p.Headings, "Practice areas") {
		t.Errorf("headings = %v", p.Headings)
	}
	if strings.Contains(p.Text, "var x=1") {
		t.Errorf("script text leaked into body: %q", p.Text)
	}
	if strings.Contains(p.Text, "Home About Contact") {
		t.Errorf("nav text leaked into body: %q", p.Text)
	}
	if !strings.Contains(p.Text, "receptionist") {
		t.Errorf("body lost signal: %q", p.Text)
	}
}

func TestReduceUsesOGDescriptionFallback(t *testing.T) {
	p := Reduce(load(t, "saas.html"))
	if !strings.HasPrefix(p.Title, "Loopwise") {
		t.Errorf("title = %q", p.Title)
	}
	if !strings.Contains(p.Description, "Self-serve product analytics") {
		t.Errorf("description = %q", p.Description)
	}
	if !contains(p.Headings, "Understand every user journey") {
		t.Errorf("headings = %v", p.Headings)
	}
}

func TestTextIsCapped(t *testing.T) {
	big := "<html><body>" + strings.Repeat("word ", 10000) + "</body></html>"
	p := Reduce(big)
	if n := len([]rune(p.Text)); n > MaxChars {
		t.Errorf("text length %d > %d", n, MaxChars)
	}
}

func TestHeadingsCapped(t *testing.T) {
	var b strings.Builder
	b.WriteString("<html><body>")
	for i := 0; i < 30; i++ {
		b.WriteString("<h2>heading</h2>")
	}
	b.WriteString("</body></html>")
	if p := Reduce(b.String()); len(p.Headings) != MaxHeadings {
		t.Errorf("headings = %d, want %d", len(p.Headings), MaxHeadings)
	}
}
