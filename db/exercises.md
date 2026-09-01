# SQL exercises against this schema

Run `uv run python db/seed.py` first, then `psql "$DATABASE_URL"`. Write your answer before opening the solution. Each one teaches something you will be asked in an interview or will need in a gig.

## 1. Warm-up: SELECT, WHERE, ORDER BY
List invoices over $300, most recent first, showing vendor and total.
<details><summary>Solution</summary>

```sql
SELECT vendor, invoice_number, invoice_date, total
FROM v_invoice
WHERE total > 300
ORDER BY invoice_date DESC;
```
Note: `v_invoice` is a view; the join to `vendor` is inside it. Try `\d+ v_invoice` to see its definition.
</details>

## 2. JOIN and GROUP BY
Total spend per vendor, highest first, including how many invoices each has.
<details><summary>Solution</summary>

```sql
SELECT v.name, count(*) AS invoices, sum(i.total) AS spend
FROM invoice i
JOIN vendor v ON v.id = i.vendor_id
GROUP BY v.name
ORDER BY spend DESC;
```
Why `GROUP BY v.name` and not `v.id`? Both work here because name is unique. Grouping by the key is the safer habit.
</details>

## 3. Aggregates over a child table
The five most expensive line items across all invoices, with their vendor.
<details><summary>Solution</summary>

```sql
SELECT v.name AS vendor, li.description, li.quantity, li.unit_price, li.amount
FROM invoice_line_item li
JOIN invoice i ON i.id = li.invoice_id
JOIN vendor v  ON v.id = i.vendor_id
ORDER BY li.amount DESC
LIMIT 5;
```
</details>

## 4. Prove the constraint works
Try to insert an invoice whose total does not add up. Read the error. Then look at the constraint definition.
<details><summary>Solution</summary>

```sql
INSERT INTO invoice (vendor_id, invoice_number, invoice_date, subtotal, tax, total)
VALUES (1, 'BAD-1', '2026-09-01', 100, 7, 999);
-- ERROR:  new row for relation "invoice" violates check constraint "invoice_total_adds_up"
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'invoice'::regclass;
```
This is why the CHECK is in the database and not only in Python: the TypeScript, Go, and n8n clients get the same protection for free.
</details>

## 5. Date arithmetic
Invoices that are overdue as of today (due date passed), with how many days late.
<details><summary>Solution</summary>

```sql
SELECT vendor, invoice_number, due_date, current_date - due_date AS days_late
FROM v_invoice
WHERE due_date < current_date
ORDER BY days_late DESC;
```
`DATE - DATE` gives an integer number of days in PostgreSQL.
</details>

## 6. Arrays
Leads whose fit reasons include "phone intake".
<details><summary>Solution</summary>

```sql
SELECT company, fit_score, fit_reasons
FROM lead
WHERE 'phone intake' = ANY (fit_reasons);
-- or: WHERE fit_reasons @> ARRAY['phone intake']
```
`@>` means "contains" and can use a GIN index if the table grows.
</details>

## 7. Conditional aggregates
Per day: how many emails, how many drafted, how many escalated. Then compare with `SELECT * FROM v_daily_triage`.
<details><summary>Solution</summary>

```sql
SELECT created_at::date AS day,
       count(*)                          AS emails,
       count(*) FILTER (WHERE drafted)   AS drafts,
       count(*) FILTER (WHERE escalated) AS escalations
FROM email_triage
GROUP BY 1
ORDER BY 1 DESC;
```
`count(*) FILTER (WHERE ...)` beats `sum(CASE WHEN ... THEN 1 ELSE 0 END)` for readability.
</details>

## 8. Window functions
Rank each invoice within its vendor by total, and show the running total of spend by date.
<details><summary>Solution</summary>

```sql
SELECT vendor, invoice_number, total,
       rank() OVER (PARTITION BY vendor ORDER BY total DESC)      AS rank_in_vendor,
       sum(total) OVER (ORDER BY invoice_date, id)                AS running_spend
FROM v_invoice
ORDER BY invoice_date, id;
```
</details>

## 9. Upsert (what every pipeline needs)
Insert a lead for a URL that already exists, updating its score instead of failing.
<details><summary>Solution</summary>

```sql
INSERT INTO lead (url, company, fit_score, scored_at)
VALUES ('https://loopwise.example', 'Loopwise', 3, now())
ON CONFLICT (url) DO UPDATE
SET fit_score = EXCLUDED.fit_score, scored_at = EXCLUDED.scored_at;
```
`EXCLUDED` is the row that would have been inserted. This is how `seed.py` and the pipelines stay idempotent.
</details>

## 10. Explain a query
Run `EXPLAIN ANALYZE` on exercise 2. Find the join method and whether an index was used. Then add 100,000 fake invoices with `generate_series` and run it again.
<details><summary>Solution</summary>

```sql
EXPLAIN ANALYZE
SELECT v.name, count(*), sum(i.total) FROM invoice i JOIN vendor v ON v.id = i.vendor_id GROUP BY v.name;

INSERT INTO invoice (vendor_id, invoice_number, invoice_date, subtotal, tax, total)
SELECT 1 + (g % 5), 'GEN-' || g, current_date - (g % 365), 100, 7, 107
FROM generate_series(1, 100000) g;

EXPLAIN ANALYZE ... -- same query; note Seq Scan vs Index Scan and the Hash Join
```
Clean up with `DELETE FROM invoice WHERE invoice_number LIKE 'GEN-%';`
</details>

## 11. Write a migration
Add a `paid_at TIMESTAMPTZ` column to `invoice` and a partial index on unpaid invoices. Put it in `db/migrations/002_invoice_paid.sql` and apply it with `migrate.py`.
<details><summary>Solution</summary>

```sql
BEGIN;
ALTER TABLE invoice ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS invoice_unpaid_idx ON invoice (due_date) WHERE paid_at IS NULL;
INSERT INTO schema_migration (version) VALUES ('002_invoice_paid') ON CONFLICT DO NOTHING;
COMMIT;
```
A partial index only stores unpaid rows, so "what is overdue" stays fast even when most invoices are paid.
</details>

## 12. Interview question
"Why is money stored as NUMERIC and not FLOAT?" Try it:
```sql
SELECT 0.1::float8 + 0.2::float8, 0.1::numeric + 0.2::numeric;
```
</details>
