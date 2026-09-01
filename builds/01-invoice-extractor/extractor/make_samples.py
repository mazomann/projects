"""Generate five synthetic invoice PDFs (fictional vendors) for testing the extractor."""
from pathlib import Path
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
import json

OUT = Path(__file__).resolve().parent.parent / "sample-data"
OUT.mkdir(exist_ok=True)

INVOICES = [
    {"file": "inv-001.pdf", "vendor": "Northwind Paper Co.", "invoice_number": "NW-10432", "date": "2026-08-03", "due": "2026-09-02",
     "items": [["A4 copy paper, 5000 sheets", 4, 38.50], ["Toner cartridge HL-2350", 2, 64.00]], "tax_rate": 0.07},
    {"file": "inv-002.pdf", "vendor": "Blue Harbor Web Hosting", "invoice_number": "BH-2026-0917", "date": "2026-08-15", "due": "2026-08-30",
     "items": [["Shared hosting, annual", 1, 143.88], ["Domain renewal example-store.com", 1, 15.99]], "tax_rate": 0.0},
    {"file": "inv-003.pdf", "vendor": "Cedar & Stone Landscaping LLC", "invoice_number": "1187", "date": "2026-07-29", "due": "2026-08-28",
     "items": [["Monthly grounds maintenance", 1, 425.00], ["Mulch, cubic yard", 3, 42.00], ["Irrigation head replacement", 6, 18.75]], "tax_rate": 0.065},
    {"file": "inv-004.pdf", "vendor": "Quantum Office Supplies", "invoice_number": "QOS-88121", "date": "2026-08-20", "due": "2026-09-19",
     "items": [["Ergonomic chair, black", 2, 219.00], ["Standing desk converter", 1, 189.99], ["Cable management kit", 5, 12.40]], "tax_rate": 0.07},
    {"file": "inv-005.pdf", "vendor": "Meridian Cleaning Services", "invoice_number": "MCS-0450", "date": "2026-08-31", "due": "2026-09-14",
     "items": [["Office cleaning, 4 visits", 4, 95.00]], "tax_rate": 0.0},
]

def build(inv):
    path = OUT / inv["file"]
    c = canvas.Canvas(str(path), pagesize=LETTER)
    w, h = LETTER
    c.setFont("Helvetica-Bold", 18); c.drawString(50, h - 60, inv["vendor"])
    c.setFont("Helvetica", 10)
    c.drawString(50, h - 78, "123 Example Street, Springfield")
    c.setFont("Helvetica-Bold", 14); c.drawRightString(w - 50, h - 60, "INVOICE")
    c.setFont("Helvetica", 10)
    c.drawRightString(w - 50, h - 78, f"Invoice #: {inv['invoice_number']}")
    c.drawRightString(w - 50, h - 92, f"Date: {inv['date']}")
    c.drawRightString(w - 50, h - 106, f"Due: {inv['due']}")
    c.drawString(50, h - 130, "Bill to: Acme Analytics Inc., 9 Data Drive, Springfield")
    y = h - 170
    c.setFont("Helvetica-Bold", 10)
    for x, t in [(50, "Description"), (350, "Qty"), (420, "Unit price"), (500, "Amount")]:
        c.drawString(x, y, t)
    c.line(50, y - 4, w - 50, y - 4)
    c.setFont("Helvetica", 10); y -= 20
    subtotal = 0.0
    for desc, qty, unit in inv["items"]:
        amt = round(qty * unit, 2); subtotal += amt
        c.drawString(50, y, desc); c.drawString(350, y, str(qty))
        c.drawRightString(480, y, f"{unit:,.2f}"); c.drawRightString(w - 50, y, f"{amt:,.2f}")
        y -= 16
    tax = round(subtotal * inv["tax_rate"], 2); total = round(subtotal + tax, 2)
    y -= 10
    c.drawRightString(480, y, "Subtotal"); c.drawRightString(w - 50, y, f"{subtotal:,.2f}"); y -= 16
    c.drawRightString(480, y, f"Tax ({inv['tax_rate']*100:g}%)"); c.drawRightString(w - 50, y, f"{tax:,.2f}"); y -= 16
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(480, y, "Total due"); c.drawRightString(w - 50, y, f"${total:,.2f}")
    c.setFont("Helvetica", 9); c.drawString(50, 60, "Payment terms: Net 30. Thank you for your business.")
    c.save()
    return {"file": inv["file"], "vendor": inv["vendor"], "invoice_number": inv["invoice_number"], "invoice_date": inv["date"],
            "due_date": inv["due"], "currency": "USD", "subtotal": round(subtotal, 2), "tax": tax, "total": total,
            "line_items": [{"description": d, "quantity": q, "unit_price": u, "amount": round(q * u, 2)} for d, q, u in inv["items"]]}

expected = [build(i) for i in INVOICES]
(OUT / "expected.json").write_text(json.dumps(expected, indent=2))
print("wrote", len(expected), "invoices to", OUT)
