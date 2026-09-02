import { describe, expect, it } from "vitest";
import { handleApi } from "../src/api.js";
import type { Db } from "../src/db.js";
import { SQL } from "../src/queries.js";

// Fake Db: records which query ran with which params, returns canned rows. No PostgreSQL needed.
function fakeDb(rows: Record<string, unknown[]> = {}) {
  const calls: { name: string; params: unknown[] }[] = [];
  const db: Db = {
    async run(name, params = []) {
      calls.push({ name, params });
      if (name === "totals" && !rows.totals) return [{ invoices: 0 }] as never;
      return (rows[name] ?? []) as never;
    },
    async close() {},
  };
  return { db, calls };
}

const u = (p: string) => new URL(p, "http://localhost");

describe("handleApi", () => {
  it("summary returns the single totals row, not an array", async () => {
    const { db } = fakeDb({ totals: [{ invoices: 5, leads: 3 }] });
    const r = await handleApi(db, u("/api/summary"));
    expect(r.status).toBe(200);
    expect(r.body).toEqual({ invoices: 5, leads: 3 });
  });

  it("passes a sane default limit and caps large ones", async () => {
    const { db, calls } = fakeDb();
    await handleApi(db, u("/api/invoices"));
    await handleApi(db, u("/api/leads?limit=99999"));
    await handleApi(db, u("/api/triage?limit=abc"));
    expect(calls.map((c) => c.params)).toEqual([[50], [500], [50]]);
  });

  it("404s unknown routes without touching the db", async () => {
    const { db, calls } = fakeDb();
    const r = await handleApi(db, u("/api/nope"));
    expect(r.status).toBe(404);
    expect(calls).toHaveLength(0);
  });

  it("turns db errors into a 500 with a message", async () => {
    const db: Db = {
      run: async () => {
        throw new Error("connection refused");
      },
      close: async () => {},
    };
    const r = await handleApi(db, u("/api/spend"));
    expect(r.status).toBe(500);
    expect(r.body).toEqual({ error: "connection refused" });
  });
});

describe("SQL", () => {
  it("never interpolates: every query uses $n placeholders or none", () => {
    for (const [name, q] of Object.entries(SQL)) {
      expect(q, name).not.toMatch(/\$\{|' \+ /);
    }
  });
  it("every list query is bounded", () => {
    for (const name of ["invoices", "leads", "triageRecent", "triageByDay"] as const) {
      expect(SQL[name]).toMatch(/LIMIT/);
    }
  });
});
