import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

export const SAMPLES = fileURLToPath(new URL("../../sample-data", import.meta.url));

export interface Expected {
  file: string;
  vendor: string;
  invoice_number: string;
  invoice_date: string;
  due_date: string | null;
  currency: string;
  subtotal: number;
  tax: number;
  total: number;
  line_items: { description: string; quantity: number; unit_price: number; amount: number }[];
}

export const EXPECTED: Expected[] = JSON.parse(readFileSync(`${SAMPLES}/expected.json`, "utf8"));

/** expected.json entry without the `file` key, i.e. what the LLM is supposed to return. */
export function sample(exp: Expected): Omit<Expected, "file"> {
  const { file: _file, ...rest } = exp;
  return structuredClone(rest);
}

/** A one-page PDF with no text layer (what a scanned invoice looks like to a text extractor). */
export function blankPdf(): Buffer {
  const objs = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>",
  ];
  let out = "%PDF-1.4\n";
  const offsets: number[] = [];
  objs.forEach((o, i) => {
    offsets.push(out.length);
    out += `${i + 1} 0 obj\n${o}\nendobj\n`;
  });
  const xref = out.length;
  out += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`;
  for (const off of offsets) out += `${String(off).padStart(10, "0")} 00000 n \n`;
  out += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(out, "latin1");
}
