"""Meridian Supply Co. — a deliberately imperfect client billing portal.

This is the zero-flake demo target. It ships inside the same deploy so the
live demo never depends on a third-party site. The mess is intentional:
mixed date formats, mixed currencies, inconsistent statuses, a duplicate
invoice number, and a credit note — exactly the kind of cleanup an
accounting agent should catch and normalize.
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(prefix="/sandbox")

USER, PASS = "demo", "meridian2026"
COOKIE = "meridian_session"

INVOICES = [
    # (number, vendor, date_as_shown, amount_as_shown, status_as_shown)
    ("INV-2041", "Northwind Traders", "03/15/2026", "$1,240.50", "Paid"),
    ("INV-2042", "Acme Industrial", "2026-03-18", "$8,900.00", "PAID"),
    ("INV-2043", "Baltic Freight GmbH", "21.03.2026", "2.450,00 EUR", "Overdue"),
    ("INV-2044", "Sunrise Office Supply", "Mar 24, 2026", "$312.75", "pending"),
    ("INV-2045", "Kestrel Logistics", "03/29/2026", "$4,150.00", "Paid"),
    ("INV-2046", "Acme Industrial", "2026-04-02", "$2,300.00", "Pending"),
    ("CN-0107",  "Acme Industrial", "2026-04-05", "-$450.00", "Credit note"),
    ("INV-2047", "Mumbai Textiles Pvt", "05 Apr 2026", "₹1,98,000", "Paid"),
    ("INV-2048", "Northwind Traders", "04/11/2026", "$1,240.50", "Paid"),
    ("INV-2049", "Baltic Freight GmbH", "14.04.2026", "1.780,00 EUR", "overdue"),
    ("INV-2050", "Sunrise Office Supply", "Apr 18, 2026", "$89.99", "Paid"),
    ("INV-2050", "Kestrel Logistics", "04/21/2026", "$6,720.00", "Pending"),  # duplicate number, real trap
    ("INV-2052", "Acme Industrial", "2026-04-25", "$12,050.00", "Overdue"),
    ("INV-2053", "Northwind Traders", "04/28/2026", "$980.25", "pending"),
]

PER_PAGE = 5


def _page(title: str, body: str) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>{title} — Meridian Supply Co.</title>
<style>
 body{{font-family:Georgia,serif;background:#f4f1ea;color:#2b2b2b;margin:0}}
 header{{background:#1e3a2f;color:#f4f1ea;padding:14px 28px;font-size:20px}}
 header small{{opacity:.7;font-size:12px;margin-left:10px}}
 main{{max-width:860px;margin:30px auto;background:#fff;padding:28px;
      border:1px solid #d8d2c4;box-shadow:2px 2px 0 #d8d2c4}}
 table{{border-collapse:collapse;width:100%;font-size:14px}}
 th,td{{border:1px solid #cfc8b8;padding:8px 10px;text-align:left}}
 th{{background:#ece7db}}
 a{{color:#1e5c3a}}
 .btn{{background:#1e3a2f;color:#fff;border:0;padding:9px 18px;cursor:pointer;font-size:14px}}
 input{{padding:8px;border:1px solid #b8b0a0;width:240px;font-size:14px}}
 label{{display:block;margin:12px 0 4px}}
 .pager{{margin-top:18px}} .pager a,.pager b{{margin-right:12px}}
 .note{{background:#fdf6dd;border:1px solid #e0d49a;padding:10px;font-size:13px;margin-bottom:16px}}
</style></head><body>
<header>Meridian Supply Co. <small>client billing portal</small></header>
<main>{body}</main></body></html>"""


def _authed(request: Request) -> bool:
    return request.cookies.get(COOKIE) == "ok"


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    if _authed(request):
        return RedirectResponse("/sandbox/invoices", status_code=302)
    return _page("Sign in", f"""
      <h2>Client sign in</h2>
      <p class="note">Demo environment. Use username <b>{USER}</b> and password
      <b>{PASS}</b>.</p>
      <form method="post" action="/sandbox/login">
        <label>Username</label><input name="username" placeholder="username">
        <label>Password</label><input name="password" type="password" placeholder="password">
        <p><button class="btn" type="submit">Sign in</button></p>
      </form>""")


@router.post("/login")
def login(username: str = Form(""), password: str = Form("")):
    if username == USER and password == PASS:
        r = RedirectResponse("/sandbox/invoices", status_code=302)
        r.set_cookie(COOKIE, "ok", httponly=True)
        return r
    return HTMLResponse(_page("Sign in", """
      <h2>Client sign in</h2>
      <p class="note" style="background:#fbe3e0;border-color:#d89a9a">
      Invalid credentials. Please try again.</p>
      <p><a href="/sandbox">Back to sign in</a></p>"""), status_code=401)


@router.get("/invoices", response_class=HTMLResponse)
def invoices(request: Request, page: int = 1):
    if not _authed(request):
        return RedirectResponse("/sandbox", status_code=302)
    pages = (len(INVOICES) + PER_PAGE - 1) // PER_PAGE
    page = max(1, min(page, pages))
    chunk = INVOICES[(page - 1) * PER_PAGE: page * PER_PAGE]
    rows = "\n".join(
        f"<tr><td><a href='/sandbox/invoices/{i}'>{n}</a></td><td>{v}</td>"
        f"<td>{d}</td><td>{a}</td><td>{s}</td></tr>"
        for i, (n, v, d, a, s) in enumerate(chunk, start=(page - 1) * PER_PAGE))
    pager = " ".join(
        f"<b>{p}</b>" if p == page else f"<a href='/sandbox/invoices?page={p}'>{p}</a>"
        for p in range(1, pages + 1))
    return _page("Invoices", f"""
      <h2>Invoices</h2>
      <p class="note">Records are shown exactly as entered by our regional
      offices. Formats may vary.</p>
      <table><tr><th>Invoice #</th><th>Vendor</th><th>Date</th>
      <th>Amount</th><th>Status</th></tr>{rows}</table>
      <p class="pager">Page: {pager}</p>
      <p><a href="/sandbox/logout">Sign out</a></p>""")


@router.get("/invoices/{idx}", response_class=HTMLResponse)
def invoice_detail(request: Request, idx: int):
    if not _authed(request):
        return RedirectResponse("/sandbox", status_code=302)
    if not 0 <= idx < len(INVOICES):
        return HTMLResponse(_page("Not found", "<h2>Invoice not found</h2>"), 404)
    n, v, d, a, s = INVOICES[idx]
    return _page(n, f"""
      <h2>Invoice {n}</h2>
      <table>
        <tr><th>Vendor</th><td>{v}</td></tr>
        <tr><th>Invoice date</th><td>{d}</td></tr>
        <tr><th>Amount</th><td>{a}</td></tr>
        <tr><th>Status</th><td>{s}</td></tr>
        <tr><th>Payment terms</th><td>Net 30</td></tr>
      </table>
      <p><a href="/sandbox/invoices">Back to invoices</a></p>""")


@router.get("/logout")
def logout():
    r = RedirectResponse("/sandbox", status_code=302)
    r.delete_cookie(COOKIE)
    return r
