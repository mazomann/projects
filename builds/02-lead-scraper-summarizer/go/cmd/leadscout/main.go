// Command leadscout scores a list of company URLs against an ideal customer
// profile (ICP) and writes a CSV sorted by fit score. Go port of
// leadscout/scout.py.
//
// Usage:
//
//	leadscout -urls urls.txt -icp "small law firms in Florida that still do intake by phone" -csv leads.csv
//	HUBSPOT_TOKEN=pat-... leadscout -urls urls.txt -icp "..." -hubspot
//
// Env: ANTHROPIC_API_KEY, LEAD_MODEL (default claude-sonnet-5), HUBSPOT_TOKEN.
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/mazomann/projects/builds/02-lead-scraper-summarizer/go/internal/hubspot"
	"github.com/mazomann/projects/builds/02-lead-scraper-summarizer/go/internal/lead"
	"github.com/mazomann/projects/builds/02-lead-scraper-summarizer/go/internal/llm"
	"github.com/mazomann/projects/builds/02-lead-scraper-summarizer/go/internal/page"
)

func main() {
	os.Exit(run(os.Args[1:]))
}

func run(args []string) int {
	fs := flag.NewFlagSet("leadscout", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	urlsFile := fs.String("urls", "", "text file, one URL per line (required)")
	icp := fs.String("icp", "", "ideal customer profile, one sentence (required)")
	csvOut := fs.String("csv", "leads.csv", "output CSV path")
	maxURLs := fs.Int("max", 50, "cost cap: max URLs per run")
	delay := fs.Float64("delay", 1.5, "seconds between fetches (be polite)")
	useHubSpot := fs.Bool("hubspot", false, "also create each company in HubSpot (needs HUBSPOT_TOKEN)")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if *urlsFile == "" || *icp == "" {
		fmt.Fprintln(os.Stderr, "leadscout: -urls and -icp are required")
		fs.Usage()
		return 2
	}

	urls, err := readURLs(*urlsFile, *maxURLs)
	if err != nil {
		fmt.Fprintf(os.Stderr, "leadscout: %v\n", err)
		return 2
	}

	client := llm.NewAnthropic(os.Getenv("ANTHROPIC_API_KEY"), os.Getenv("LEAD_MODEL"))
	token := os.Getenv("HUBSPOT_TOKEN")
	if *useHubSpot && token == "" {
		fmt.Fprintln(os.Stderr, "leadscout: -hubspot set but HUBSPOT_TOKEN is empty; skipping HubSpot")
	}

	ctx := context.Background()
	var rows []lead.Row
	failed := 0
	for i, u := range urls {
		row, err := score(ctx, client, u, *icp)
		if err == nil && *useHubSpot && token != "" {
			row.HubSpotID, err = hubspot.CreateCompany(ctx, token, u, row.Assessment)
		}
		if err != nil {
			failed++
			fmt.Fprintf(os.Stderr, "[%d/%d] FAILED %s: %v\n", i+1, len(urls), u, err)
		} else {
			rows = append(rows, row)
			fmt.Fprintf(os.Stderr, "[%d/%d] %2d  %s\n", i+1, len(urls), row.FitScore, row.Company)
		}
		if i < len(urls)-1 {
			time.Sleep(time.Duration(*delay * float64(time.Second)))
		}
	}

	if len(rows) > 0 {
		if err := writeCSV(*csvOut, rows); err != nil {
			fmt.Fprintf(os.Stderr, "leadscout: write %s: %v\n", *csvOut, err)
			return 1
		}
	}
	fmt.Printf("%d scored, %d failed -> %s\n", len(rows), failed, *csvOut)
	if failed > 0 && len(rows) == 0 {
		return 1
	}
	return 0
}

// score runs fetch -> reduce -> assess for one URL.
func score(ctx context.Context, c llm.Client, u, icp string) (lead.Row, error) {
	p, err := page.Scrape(ctx, u)
	if err != nil {
		return lead.Row{}, err
	}
	a, err := c.Assess(ctx, p, icp)
	if err != nil {
		return lead.Row{}, err
	}
	return lead.Row{URL: u, Assessment: a}, nil
}

// readURLs loads non-empty, non-comment lines and applies the cap.
func readURLs(path string, limit int) ([]string, error) {
	src, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var urls []string
	for _, line := range strings.Split(string(src), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		urls = append(urls, line)
	}
	if limit >= 0 && len(urls) > limit {
		urls = urls[:limit]
	}
	return urls, nil
}

func writeCSV(path string, rows []lead.Row) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	if err := lead.WriteCSV(f, rows); err != nil {
		f.Close()
		return err
	}
	return f.Close()
}
