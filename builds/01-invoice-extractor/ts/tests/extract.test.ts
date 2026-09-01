/** Pipeline tests with a fake LLM: no API key, no network. */
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { z } from "zod";
import { extract, type Llm } from "../src/extract.js";
import { EXPECTED, SAMPLES, blankPdf, sample } from "./helpers.js";

const first = EXPECTED[0]!;

function fakeLlmFor(file: string): Llm {
  const exp = EXPECTED.find((e) => e.file === file)!;
  return async () => sample(exp);
}

describe("extract()", () => {
  it.each(EXPECTED.map((e) => [e.file] as const))("end to end with fake llm: %s", async (file) => {
    const inv = await extract(join(SAMPLES, file), fakeLlmFor(file));
    const exp = EXPECTED.find((e) => e.file === file)!;
    expect(inv.total).toBe(exp.total);
    expect(inv.vendor).toBe(exp.vendor);
  });

  it("retry feeds the validation error back into the prompt", async () => {
    const calls: string[] = [];
    const flaky: Llm = async (text) => {
      calls.push(text);
      const raw = sample(first);
      if (calls.length === 1) raw.total = 1.0; // wrong on first pass
      return raw;
    };
    const inv = await extract(join(SAMPLES, first.file), flaky);
    expect(calls).toHaveLength(2);
    expect(calls[0]).not.toContain("failed validation");
    expect(calls[1]).toContain("failed validation");
    expect(calls[1]).toContain(`subtotal ${first.subtotal} + tax ${first.tax} != total 1`);
    expect(calls[1]).toContain("Return a corrected extraction");
    expect(calls[1]!.startsWith(calls[0]!)).toBe(true); // original text is kept
    expect(inv.total).toBe(first.total);
  });

  it("gives up after the retry", async () => {
    let n = 0;
    const alwaysWrong: Llm = async () => {
      n++;
      return { ...sample(first), total: 1.0 };
    };
    await expect(extract(join(SAMPLES, first.file), alwaysWrong)).rejects.toThrow(/total/);
    expect(n).toBe(2);
  });

  it("respects retries=0", async () => {
    let n = 0;
    const alwaysWrong: Llm = async () => {
      n++;
      return { ...sample(first), total: 1.0 };
    };
    await expect(extract(join(SAMPLES, first.file), alwaysWrong, 0)).rejects.toThrow(z.ZodError);
    expect(n).toBe(1);
  });

  it("detects scanned PDFs before calling the llm", async () => {
    const dir = mkdtempSync(join(tmpdir(), "inv-"));
    const p = join(dir, "blank.pdf");
    writeFileSync(p, blankPdf());
    let called = false;
    const llm: Llm = async () => {
      called = true;
      return {};
    };
    await expect(extract(p, llm)).rejects.toThrow(/scanned/);
    expect(called).toBe(false);
  });
});
