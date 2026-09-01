/**
 * Invoice schema and validation. Mirrors ../extractor/schema.py: the zod schema is what we
 * trust, JSON_SCHEMA is what the LLM is constrained to. Keep the two in sync.
 */
import { z } from "zod";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** "YYYY-MM-DD" -> comparable number (days are compared lexicographically-safe as ms since epoch). */
function dateMs(s: string): number {
  return Date.parse(`${s}T00:00:00Z`);
}

const isoDate = z
  .string()
  .regex(ISO_DATE, "expected ISO 8601 date, YYYY-MM-DD")
  .refine((s) => !Number.isNaN(dateMs(s)), "invalid calendar date");

const round2 = (n: number): number => Math.round(n * 100) / 100;

export const LineItem = z.object({
  description: z.string().min(1),
  quantity: z.number().gt(0),
  unit_price: z.number().min(0),
  amount: z.number().min(0),
});
export type LineItem = z.infer<typeof LineItem>;

export const Invoice = z
  .object({
    vendor: z.string().min(1),
    invoice_number: z.string().min(1),
    invoice_date: isoDate,
    due_date: isoDate.nullable().default(null),
    currency: z
      .string()
      .min(3)
      .max(3)
      .default("USD")
      .transform((v) => v.toUpperCase()),
    subtotal: z.number().min(0),
    tax: z.number().min(0),
    total: z.number().min(0),
    line_items: z.array(LineItem).min(1),
  })
  .superRefine((inv, ctx) => {
    // Totals must add up. Catches the most common LLM extraction mistakes.
    const items = round2(inv.line_items.reduce((sum, li) => sum + li.amount, 0));
    if (Math.abs(items - inv.subtotal) > 0.02) {
      ctx.addIssue({
        code: "custom",
        path: ["subtotal"],
        message: `line items sum to ${items}, subtotal says ${inv.subtotal}`,
      });
    }
    if (Math.abs(round2(inv.subtotal + inv.tax) - inv.total) > 0.02) {
      ctx.addIssue({
        code: "custom",
        path: ["total"],
        message: `subtotal ${inv.subtotal} + tax ${inv.tax} != total ${inv.total}`,
      });
    }
    if (inv.due_date !== null && dateMs(inv.due_date) < dateMs(inv.invoice_date)) {
      ctx.addIssue({ code: "custom", path: ["due_date"], message: "due_date before invoice_date" });
    }
  });
export type Invoice = z.infer<typeof Invoice>;

/** Flat row for a spreadsheet: one row per invoice, line items joined. Same shape as Invoice.to_row(). */
export function toRow(inv: Invoice): Record<string, string | number> {
  return {
    vendor: inv.vendor,
    invoice_number: inv.invoice_number,
    invoice_date: inv.invoice_date,
    due_date: inv.due_date ?? "",
    currency: inv.currency,
    subtotal: inv.subtotal,
    tax: inv.tax,
    total: inv.total,
    line_items: inv.line_items
      .map((li) => `${fmtG(li.quantity)} x ${li.description} @ ${li.unit_price.toFixed(2)}`)
      .join("; "),
  };
}

/** Python's `%g`-ish formatting for quantities: 4 -> "4", 1.5 -> "1.5". */
function fmtG(n: number): string {
  return Number.isInteger(n) ? String(n) : String(Number(n.toPrecision(6)));
}

// JSON schema handed to the LLM (strict: no extra keys, everything required so nothing is silently skipped).
// Identical to extractor/schema.py JSON_SCHEMA.
export const JSON_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: [
    "vendor",
    "invoice_number",
    "invoice_date",
    "due_date",
    "currency",
    "subtotal",
    "tax",
    "total",
    "line_items",
  ],
  properties: {
    vendor: { type: "string" },
    invoice_number: { type: "string" },
    invoice_date: { type: "string", description: "ISO 8601 date, YYYY-MM-DD" },
    due_date: { type: ["string", "null"], description: "ISO 8601 date or null if absent" },
    currency: { type: "string", description: "ISO 4217 code, e.g. USD" },
    subtotal: { type: "number" },
    tax: { type: "number" },
    total: { type: "number" },
    line_items: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["description", "quantity", "unit_price", "amount"],
        properties: {
          description: { type: "string" },
          quantity: { type: "number" },
          unit_price: { type: "number" },
          amount: { type: "number" },
        },
      },
    },
  },
} as const;
