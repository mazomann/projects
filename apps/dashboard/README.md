# Dashboard

One page over the `automations` PostgreSQL database: totals, invoices, spend by vendor, scored leads, inbox triage. Node 24, TypeScript, the `pg` driver, plain HTML with fetch. No framework, no ORM, so every query is readable SQL in [src/queries.ts](src/queries.ts).

```bash
npm install
npm test            # API routing + SQL hygiene tests, no database needed
npm run typecheck
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/automations npm start   # http://localhost:3000
```

Run `uv run python db/migrate.py` and `db/seed.py` from the repo root first, or the tables will be empty.

## Why it is built this way

- **SQL is the point.** The heading of each panel shows the query shape it runs. Reading `queries.ts` top to bottom is a tour of the schema.
- **`handleApi` is pure**: it takes a URL and a `Db` interface and returns `{status, body}`. The tests pass a fake `Db`, so they run in milliseconds without PostgreSQL. The HTTP server is a thin shell around it.
- **Limits are enforced server-side** (default 50, cap 500) and NUMERIC values are formatted in the browser, never summed in JavaScript.
- **Auto-refreshes every 30 s**, so a pipeline run shows up while you watch.
