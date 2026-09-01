package lead

import (
	"bytes"
	"encoding/csv"
	"encoding/json"
	"strings"
	"testing"
)

func valid() Assessment {
	return Assessment{
		Company: "Harbor & Pike Law", Summary: "Three-attorney family law firm in Fort Myers.",
		FitScore: 9, FitReasons: []string{"phone intake", "small firm"},
		Opener: "Saw that your receptionist takes intake details.", RedFlags: []string{},
	}
}

func TestValidateAccepts(t *testing.T) {
	if err := valid().Validate(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestValidateRejectsOutOfRangeScore(t *testing.T) {
	a := valid()
	a.FitScore = 11
	if err := a.Validate(); err == nil {
		t.Fatal("score 11 accepted")
	}
	a.FitScore = 0
	if err := a.Validate(); err == nil {
		t.Fatal("score 0 accepted")
	}
}

func TestValidateRejectsEmptyFieldsAndTooManyReasons(t *testing.T) {
	a := valid()
	a.Company = " "
	if err := a.Validate(); err == nil || !strings.Contains(err.Error(), "company") {
		t.Errorf("empty company: %v", err)
	}
	a = valid()
	a.Opener = ""
	if err := a.Validate(); err == nil || !strings.Contains(err.Error(), "opener") {
		t.Errorf("empty opener: %v", err)
	}
	a = valid()
	a.FitReasons = []string{"a", "b", "c", "d", "e"}
	if err := a.Validate(); err == nil || !strings.Contains(err.Error(), "fit_reasons") {
		t.Errorf("five reasons: %v", err)
	}
}

func TestSchemaIsValidJSON(t *testing.T) {
	var m map[string]any
	if err := json.Unmarshal(Schema, &m); err != nil {
		t.Fatal(err)
	}
	if m["additionalProperties"] != false {
		t.Errorf("additionalProperties = %v", m["additionalProperties"])
	}
}

func TestWriteCSVSortedByScore(t *testing.T) {
	mk := func(url string, score int) Row {
		a := valid()
		a.FitScore = score
		a.Company = url
		return Row{URL: url, Assessment: a}
	}
	rows := []Row{mk("https://c.test", 3), mk("https://a.test", 9), mk("https://b.test", 5)}
	var buf bytes.Buffer
	if err := WriteCSV(&buf, rows); err != nil {
		t.Fatal(err)
	}
	recs, err := csv.NewReader(&buf).ReadAll()
	if err != nil {
		t.Fatal(err)
	}
	if got := strings.Join(recs[0], ","); got != "url,company,summary,fit_score,fit_reasons,opener,red_flags" {
		t.Errorf("header = %s", got)
	}
	wantOrder := []string{"9", "5", "3"}
	for i, want := range wantOrder {
		if recs[i+1][3] != want {
			t.Errorf("row %d score = %s, want %s", i, recs[i+1][3], want)
		}
	}
	if recs[1][4] != "phone intake | small firm" {
		t.Errorf("fit_reasons joined = %q", recs[1][4])
	}
}

func TestWriteCSVAddsHubSpotColumnWhenPresent(t *testing.T) {
	rows := []Row{{URL: "https://a.test", HubSpotID: "123", Assessment: valid()}}
	var buf bytes.Buffer
	if err := WriteCSV(&buf, rows); err != nil {
		t.Fatal(err)
	}
	recs, _ := csv.NewReader(&buf).ReadAll()
	if recs[0][len(recs[0])-1] != "hubspot_id" || recs[1][len(recs[1])-1] != "123" {
		t.Errorf("hubspot column missing: %v", recs)
	}
}
