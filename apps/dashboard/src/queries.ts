// Every query the dashboard runs, as plain SQL. Kept in one file so it doubles as a reading list.
// Parameters use $1, $2 placeholders; nothing is ever string-concatenated into SQL.

export const SQL = {
  invoices: `
    SELECT id, vendor, invoice_number, invoice_date, due_date, currency, subtotal, tax, total, line_count,
           CASE WHEN due_date < current_date THEN current_date - due_date ELSE 0 END AS days_late
    FROM v_invoice
    ORDER BY invoice_date DESC, id DESC
    LIMIT $1`,

  spendByVendor: `
    SELECT v.name AS vendor, count(*)::int AS invoices, sum(i.total) AS spend
    FROM invoice i JOIN vendor v ON v.id = i.vendor_id
    GROUP BY v.name
    ORDER BY spend DESC`,

  leads: `
    SELECT id, url, company, summary, fit_score, fit_reasons, opener, red_flags, hubspot_id, error, scored_at
    FROM lead
    ORDER BY fit_score DESC NULLS LAST, scored_at DESC
    LIMIT $1`,

  triageRecent: `
    SELECT id, sender, subject, received_at, category, confidence, urgency, summary, drafted, escalated
    FROM email_triage
    ORDER BY received_at DESC NULLS LAST, id DESC
    LIMIT $1`,

  triageByDay: `SELECT day, category, emails::int, drafts::int, escalations::int FROM v_daily_triage LIMIT 60`,

  totals: `
    SELECT (SELECT count(*)::int FROM invoice)                                  AS invoices,
           (SELECT coalesce(sum(total), 0) FROM invoice)                        AS invoice_spend,
           (SELECT count(*)::int FROM lead WHERE fit_score >= 7)                AS good_leads,
           (SELECT count(*)::int FROM lead)                                     AS leads,
           (SELECT count(*)::int FROM email_triage WHERE category = 'needs_human') AS needs_human,
           (SELECT count(*)::int FROM email_triage)                             AS emails`,
} as const;

export type QueryName = keyof typeof SQL;
