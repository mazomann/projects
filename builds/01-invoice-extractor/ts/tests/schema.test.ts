import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { z } from "zod";
import { Invoice, JSON_SCHEMA, toRow } from "../src/schema.js";
import { pdfToText } from "../src/pdfText.js";
import { EXPECTED, SAMPLES, sample } from "./helpers.js";

describe("Invoice schema", () => {
  it.each(EXPECTED.map((e) => [e.file, e] as const))("expected sample %s validates", (_file, exp) => {
    const inv = Invoice.parse(sample(exp));
    expect(inv.total).toBe(exp.total);
    const row = toRow(inv);
    expect(row.vendor).toBe(exp.vendor);
    if (exp.line_items.length > 1) expect(String(row.line_items)).toContain(";");
  });

  it("rejects mismatched totals", () => {
    const bad = { ...sample(EXPECTED[0]!), total: EXPECTED[0]!.total + 10 };
    const r = Invoice.safeParse(bad);
    expect(r.success).toBe(false);
    expect(r.error?.issues.map((i) => i.message).join("\n")).toMatch(/total/);
  });

  it("rejects line items that do not sum to subtotal", () => {
    const bad = { ...sample(EXPECTED[0]!), subtotal: 1 };
    const r = Invoice.safeParse(bad);
    expect(r.success).toBe(false);
    expect(r.error?.issues[0]?.message).toMatch(/line items sum/);
  });

  it("rejects due_date before invoice_date", () => {
    const bad = { ...sample(EXPECTED[0]!), due_date: "2020-01-01" };
    const r = Invoice.safeParse(bad);
    expect(r.success).toBe(false);
    expect(r.error?.issues.map((i) => i.message).join("\n")).toMatch(/due_date/);
  });

  it("uppercases currency", () => {
    const ok = { ...sample(EXPECTED[1]!), currency: "usd" };
    expect(Invoice.parse(ok).currency).toBe("USD");
  });

  it("toRow matches the Python to_row() format", () => {
    const row = toRow(Invoice.parse(sample(EXPECTED[0]!)));
    expect(row).toEqual({
      vendor: "Northwind Paper Co.",
      invoice_number: "NW-10432",
      invoice_date: "2026-08-03",
      due_date: "2026-09-02",
      currency: "USD",
      subtotal: 282,
      tax: 19.74,
      total: 301.74,
      line_items: "4 x A4 copy paper, 5000 sheets @ 38.50; 2 x Toner cartridge HL-2350 @ 64.00",
    });
  });

  it("JSON_SCHEMA is identical to the Python one", () => {
    // Regenerate from the Python source so the two twins cannot drift silently.
    const py = readFileSync(new URL("../../extractor/schema.py", import.meta.url), "utf8");
    const start = py.indexOf("JSON_SCHEMA = {");
    const literal = py
      .slice(start + "JSON_SCHEMA = ".length)
      .replace(/\bFalse\b/g, "false")
      .replace(/\bTrue\b/g, "true")
      .replace(/,(\s*[}\]])/g, "$1");
    const pySchema = JSON.parse(literal.trim()) as unknown;
    expect(JSON_SCHEMA).toEqual(pySchema);
  });

  it("ZodError is the error type callers can catch", () => {
    expect(() => Invoice.parse({})).toThrow(z.ZodError);
  });
});

describe("pdfToText", () => {
  it.each(EXPECTED.map((e) => [e.file, e] as const))("%s text contains key fields", async (file, exp) => {
    const text = await pdfToText(`${SAMPLES}/${file}`);
    expect(text).toContain(exp.vendor);
    expect(text).toContain(exp.invoice_number);
    expect(text).toContain(exp.total.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
  });
});
