/**
 * PDF invoice -> validated Invoice. The LLM call is a plain function so it can be swapped or faked.
 *
 * Env:
 *   ANTHROPIC_API_KEY   required for the real LLM call
 *   INVOICE_MODEL       default claude-sonnet-5
 */
import Anthropic from "@anthropic-ai/sdk";
import { z } from "zod";
import { pdfToText } from "./pdfText.js";
import { Invoice, JSON_SCHEMA } from "./schema.js";

const SYSTEM =
  "You extract structured data from invoice text. Return only the fields in the schema. " +
  "Dates as YYYY-MM-DD. Amounts as plain numbers without currency symbols. " +
  "line_items amount = quantity * unit_price. subtotal = sum of amounts. total = subtotal + tax. " +
  "If a field is genuinely absent use null (due_date) or 0 (tax). Do not invent values.";

/** invoice text -> raw object matching JSON_SCHEMA (validated afterwards by zod). */
export type Llm = (text: string) => Promise<unknown>;

/** Real call: Claude structured output constrained to JSON_SCHEMA. */
export const claudeLlm: Llm = async (text) => {
  const client = new Anthropic(); // reads ANTHROPIC_API_KEY
  const resp = await client.messages.create({
    model: process.env.INVOICE_MODEL ?? "claude-sonnet-5",
    max_tokens: 2048,
    system: SYSTEM,
    messages: [{ role: "user", content: `<invoice>\n${text}\n</invoice>` }],
    output_config: { format: { type: "json_schema" as const, schema: JSON_SCHEMA } },
  });
  if (resp.stop_reason === "refusal") {
    throw new Error("model refused the request");
  }
  const block = resp.content.find((b) => b.type === "text");
  if (!block) {
    throw new Error("model returned no text block");
  }
  return JSON.parse(block.text) as unknown;
};

/**
 * Extract and validate. On a validation failure, retry once with the error fed back
 * (LLMs fix arithmetic on a second pass).
 */
export async function extract(pdfPath: string, llm: Llm = claudeLlm): Promise<Invoice> {
  const text = await pdfToText(pdfPath);
  const first = Invoice.safeParse(await llm(text));
  if (first.success) return first.data;
  const retry =
    `${text}\n\nYour previous extraction failed validation:\n${formatZodError(first.error)}\n` +
    "Return a corrected extraction.";
  return Invoice.parse(await llm(retry));
}

/** One line per issue, like pydantic's error text: "total: subtotal 1 + tax 2 != total 3". */
export function formatZodError(err: z.ZodError): string {
  return err.issues.map((i) => `${i.path.join(".") || "(root)"}: ${i.message}`).join("\n");
}
