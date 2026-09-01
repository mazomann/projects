import type { Db } from "./db.js";

// Pure routing: takes a path, returns {status, body}. No HTTP objects, so it is trivially unit-tested.
export type ApiResult = { status: number; body: unknown };

const LIMIT_MAX = 500;

function limitFrom(url: URL): number {
  const n = Number(url.searchParams.get("limit") ?? 50);
  return Number.isFinite(n) && n > 0 ? Math.min(Math.floor(n), LIMIT_MAX) : 50;
}

export async function handleApi(db: Db, url: URL): Promise<ApiResult> {
  try {
    switch (url.pathname) {
      case "/api/summary": {
        const [totals] = await db.run("totals");
        return { status: 200, body: totals };
      }
      case "/api/invoices":
        return { status: 200, body: await db.run("invoices", [limitFrom(url)]) };
      case "/api/spend":
        return { status: 200, body: await db.run("spendByVendor") };
      case "/api/leads":
        return { status: 200, body: await db.run("leads", [limitFrom(url)]) };
      case "/api/triage":
        return { status: 200, body: await db.run("triageRecent", [limitFrom(url)]) };
      case "/api/triage/daily":
        return { status: 200, body: await db.run("triageByDay") };
      default:
        return { status: 404, body: { error: "not found" } };
    }
  } catch (e) {
    return { status: 500, body: { error: e instanceof Error ? e.message : String(e) } };
  }
}
