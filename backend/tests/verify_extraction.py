"""Ground-truth verification: did the agent extract the data CORRECTLY?

The loop test proves the machinery runs. This proves the output is right —
a different and harder question. It re-derives the expected normalization
independently from the sandbox's source data and compares field by field,
so a plausible-looking-but-wrong table fails loudly.

Usage:
    python tests/verify_extraction.py results.json

where results.json is the `result` event from a run (or paste the table).
With no argument it verifies the recorded production run below.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.sandbox import INVOICES  # noqa: E402

DATE_FORMATS = ("%m/%d/%Y", "%Y-%m-%d", "%d.%m.%Y", "%b %d, %Y", "%d %b %Y")


def norm_date(raw: str) -> str:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"unparseable date: {raw!r}")


def norm_amount(raw: str) -> tuple[float, str]:
    raw = raw.strip()
    if "EUR" in raw:                      # 2.450,00 EUR  (dot=thousands, comma=decimal)
        return float(raw.replace("EUR", "").strip().replace(".", "").replace(",", ".")), "EUR"
    if "₹" in raw:                        # ₹1,98,000  (lakh grouping)
        return float(raw.replace("₹", "").replace(",", "")), "INR"
    return float(raw.replace("$", "").replace(",", "")), "USD"


def norm_status(raw: str) -> str:
    s = raw.lower()
    for key, out in (("credit", "Credit"), ("paid", "Paid"),
                     ("pend", "Pending"), ("overdue", "Overdue")):
        if key in s:
            return out
    raise ValueError(f"unknown status: {raw!r}")


def expected_rows() -> list[list[str]]:
    rows = []
    for number, vendor, date, amount, status in INVOICES:
        value, currency = norm_amount(amount)
        rows.append([number, vendor, norm_date(date), f"{value:.2f}",
                     currency, norm_status(status)])
    return rows


# The table produced by the deployed agent on 2026-08-02 (Claude Sonnet,
# autopilot, 9 steps). Replace with a fresh run's rows to re-verify.
RECORDED_RUN = [
    ["INV-2041", "Northwind Traders", "2026-03-15", "1240.50", "USD", "Paid"],
    ["INV-2042", "Acme Industrial", "2026-03-18", "8900.00", "USD", "Paid"],
    ["INV-2043", "Baltic Freight GmbH", "2026-03-21", "2450.00", "EUR", "Overdue"],
    ["INV-2044", "Sunrise Office Supply", "2026-03-24", "312.75", "USD", "Pending"],
    ["INV-2045", "Kestrel Logistics", "2026-03-29", "4150.00", "USD", "Paid"],
    ["INV-2046", "Acme Industrial", "2026-04-02", "2300.00", "USD", "Pending"],
    ["CN-0107", "Acme Industrial", "2026-04-05", "-450.00", "USD", "Credit"],
    ["INV-2047", "Mumbai Textiles Pvt", "2026-04-05", "198000.00", "INR", "Paid"],
    ["INV-2048", "Northwind Traders", "2026-04-11", "1240.50", "USD", "Paid"],
    ["INV-2049", "Baltic Freight GmbH", "2026-04-14", "1780.00", "EUR", "Overdue"],
    ["INV-2050", "Sunrise Office Supply", "2026-04-18", "89.99", "USD", "Paid"],
    ["INV-2050", "Kestrel Logistics", "2026-04-21", "6720.00", "USD", "Pending"],
    ["INV-2052", "Acme Industrial", "2026-04-25", "12050.00", "USD", "Overdue"],
    ["INV-2053", "Northwind Traders", "2026-04-28", "980.25", "USD", "Pending"],
]

FIELDS = ["invoice number", "vendor", "date", "amount", "currency", "status"]


def verify(actual: list[list[str]]) -> int:
    expected = expected_rows()
    failures = 0

    if len(actual) != len(expected):
        print(f"FAIL row count: expected {len(expected)}, agent produced {len(actual)}")
        failures += 1

    for i, (exp, act) in enumerate(zip(expected, actual)):
        for field, e, a in zip(FIELDS, exp, act):
            if str(e).strip() != str(a).strip():
                print(f"FAIL row {i + 1} [{field}]: expected {e!r}, agent gave {a!r}")
                failures += 1

    checked = len(expected) * len(FIELDS)
    if failures == 0:
        print(f"PASS — {len(actual)} rows x {len(FIELDS)} fields = {checked} values, "
              "all match ground truth derived independently from source data.")
        print("Includes the deliberate traps: duplicate invoice number INV-2050, "
              "credit note CN-0107 (negative), 4 date formats, 3 currencies, "
              "inconsistent status casing.")
    else:
        print(f"\n{failures} FAILURES out of {checked} values checked.")
    return failures


if __name__ == "__main__":
    if len(sys.argv) > 1:
        payload = json.loads(Path(sys.argv[1]).read_text())
        rows = payload.get("table", payload).get("rows", payload)
        print(f"Verifying {len(rows)} rows from {sys.argv[1]}\n")
    else:
        rows = RECORDED_RUN
        print("Verifying the recorded production run (2026-08-02)\n")
    sys.exit(1 if verify(rows) else 0)
