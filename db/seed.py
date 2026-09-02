"""Load sample data so the dashboard and the SQL exercises have something to query.

Usage: DATABASE_URL=... uv run python db/seed.py
Idempotent: uses ON CONFLICT so it can be re-run.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_URL = "postgresql://postgres:postgres@localhost:5432/automations"


def returned_id(cur: psycopg.Cursor) -> Any:
    """First column of a RETURNING row. Fails loudly rather than indexing None."""
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("expected a row from a RETURNING clause, got none")
    return row[0]


def seed_invoices(conn: psycopg.Connection) -> int:
    expected = json.loads((ROOT / "builds/01-invoice-extractor/sample-data/expected.json").read_text())
    n = 0
    for inv in expected:
        vendor_id = returned_id(
            conn.execute(
                "INSERT INTO vendor (name) VALUES (%s)"
                " ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id",
                (inv["vendor"],),
            )
        )
        invoice_id = returned_id(
            conn.execute(
                """
            INSERT INTO invoice (vendor_id, invoice_number, invoice_date, due_date, currency,
                                 subtotal, tax, total, source_file, extracted_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'seed')
            ON CONFLICT (vendor_id, invoice_number) DO UPDATE SET total = EXCLUDED.total
            RETURNING id
            """,
                (
                    vendor_id,
                    inv["invoice_number"],
                    inv["invoice_date"],
                    inv["due_date"],
                    inv["currency"],
                    inv["subtotal"],
                    inv["tax"],
                    inv["total"],
                    inv["file"],
                ),
            )
        )
        conn.execute("DELETE FROM invoice_line_item WHERE invoice_id = %s", (invoice_id,))
        for pos, li in enumerate(inv["line_items"], start=1):
            conn.execute(
                "INSERT INTO invoice_line_item (invoice_id, position, description, quantity, unit_price, amount)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                (invoice_id, pos, li["description"], li["quantity"], li["unit_price"], li["amount"]),
            )
        n += 1
    return n


def seed_leads(conn: psycopg.Connection) -> int:
    rows = [
        (
            "https://harborpike.example",
            "Harbor & Pike Law",
            "Three-attorney family law firm in Fort Myers doing phone intake via a receptionist.",
            9,
            ["phone intake", "small firm", "local"],
            "Saw that your receptionist takes intake details and an attorney calls back within a day.",
            [],
        ),
        (
            "https://loopwise.example",
            "Loopwise",
            "Self-serve SaaS analytics company, 120 employees, no sales call needed.",
            2,
            ["not a services business"],
            "Noticed Loopwise is fully self-serve with a free tier.",
            ["self-serve product, no intake process"],
        ),
        (
            "https://meridian-clean.example",
            "Meridian Cleaning Services",
            "Commercial cleaning company taking bookings by phone and email.",
            7,
            ["email intake", "recurring service"],
            "Your booking form says replies take a business day; that gap is automatable.",
            [],
        ),
    ]
    for url, company, summary, score, reasons, opener, flags in rows:
        conn.execute(
            """
            INSERT INTO lead (url, company, summary, fit_score, fit_reasons, opener, red_flags, icp, scored_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (url) DO UPDATE SET fit_score = EXCLUDED.fit_score, scored_at = now()
            """,
            (
                url,
                company,
                summary,
                score,
                reasons,
                opener,
                flags,
                "small professional-services firms with phone or email intake",
            ),
        )
    return len(rows)


def seed_triage(conn: psycopg.Connection) -> int:
    inbox = json.loads((ROOT / "builds/03-inbox-triage/sample-data/inbox.json").read_text())
    decisions = {
        "m1": (
            "support",
            0.95,
            "normal",
            "Existing client locked out of portal after password resets.",
            "Hi Dana, sorry about the lockout. Someone will reset your access today.",
            True,
            False,
        ),
        "m2": (
            "sales",
            0.90,
            "normal",
            "6-person landscaping company wants a bookkeeping quote.",
            "Hi Mike, thanks for reaching out. Would Wednesday afternoon work for a call?",
            True,
            False,
        ),
        "m3": (
            "billing",
            0.92,
            "high",
            "Vendor final notice: invoice 4471, $1,240 overdue 30 days.",
            None,
            False,
            False,
        ),
        "m4": ("spam", 0.98, "low", "Unsolicited AI lead-gen promotion.", None, False, False),
        "m5": (
            "needs_human",
            0.97,
            "high",
            "Client angry about missed Friday report, mentions lawyer.",
            None,
            False,
            True,
        ),
    }
    for e in inbox:
        cat, conf, urg, summary, draft, drafted, escalated = decisions[e["id"]]
        conn.execute(
            """
            INSERT INTO email_triage (message_id, thread_id, sender, subject, received_at, category,
                                      confidence, urgency, summary, draft_reply, reason, drafted, escalated)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'seed', %s, %s)
            ON CONFLICT (message_id) DO NOTHING
            """,
            (
                e["id"],
                "t-" + e["id"],
                e["from"],
                e["subject"],
                datetime.fromisoformat(e["date"].replace("Z", "+00:00")).astimezone(UTC),
                cat,
                conf,
                urg,
                summary,
                draft,
                drafted,
                escalated,
            ),
        )
    return len(inbox)


def main() -> int:
    url = os.environ.get("DATABASE_URL", DEFAULT_URL)
    with psycopg.connect(url) as conn:
        a, b, c = seed_invoices(conn), seed_leads(conn), seed_triage(conn)
        conn.commit()
    print(f"seeded {a} invoices, {b} leads, {c} triaged emails")
    return 0


if __name__ == "__main__":
    sys.exit(main())
