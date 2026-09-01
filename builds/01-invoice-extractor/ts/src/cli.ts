/**
 * CLI, same interface as `python -m extractor.extract`:
 *
 *   npm run extract -- ../sample-data/inv-001.pdf                 # prints JSON
 *   npm run extract -- ../sample-data/*.pdf --csv out.csv         # one row per invoice, appended
 */
import { appendFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { basename } from "node:path";
import { parseArgs } from "node:util";
import { z } from "zod";
import { extract, formatZodError } from "./extract.js";
import { toRow } from "./schema.js";

function csvCell(v: string | number): string {
  const s = String(v);
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function describe(e: unknown): string {
  if (e instanceof z.ZodError) return formatZodError(e);
  if (e instanceof Error) return e.message;
  return String(e);
}

export async function main(argv: string[]): Promise<number> {
  const { values, positionals } = parseArgs({
    args: argv,
    options: { csv: { type: "string" } },
    allowPositionals: true,
  });
  if (positionals.length === 0) {
    console.error("usage: extract <pdf>... [--csv out.csv]");
    return 2;
  }
  const rows: Record<string, string | number>[] = [];
  let failures = 0;
  for (const p of positionals) {
    try {
      const inv = await extract(p);
      rows.push({ ...toRow(inv), file: basename(p) });
    } catch (e) {
      failures++;
      console.error(`FAILED ${p}: ${describe(e)}`);
    }
  }
  if (values.csv) {
    const isNew = !existsSync(values.csv);
    const fields = rows[0] ? Object.keys(rows[0]) : ["file"];
    const lines = rows.map((r) => fields.map((f) => csvCell(r[f] ?? "")).join(","));
    if (isNew) lines.unshift(fields.join(","));
    const body = lines.length ? lines.join("\r\n") + "\r\n" : "";
    if (isNew) await writeFile(values.csv, body, "utf8");
    else await appendFile(values.csv, body, "utf8");
    console.log(`wrote ${rows.length} rows to ${values.csv}, ${failures} failed`);
  } else {
    console.log(JSON.stringify(rows, null, 2));
  }
  return failures ? 1 : 0;
}

const isDirectRun = process.argv[1] !== undefined && import.meta.url === new URL(`file:///${process.argv[1].replace(/\\/g, "/")}`).href;
if (isDirectRun) {
  // Set exitCode rather than calling process.exit(): pdf.js keeps a worker around for a tick after
  // destroy(), and a hard exit while it closes trips a libuv assertion on Windows.
  main(process.argv.slice(2)).then((code) => {
    process.exitCode = code;
  });
}
