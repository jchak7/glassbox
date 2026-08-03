# EDGAR ground truth — recorded 2026-08-02 via live recon (Jay's Chrome)

Use these to verify the agent's post-deploy EDGAR runs. Source pages verified
by hand; values are as filed.

## Apple Inc — 10-K filed 2025-10-31, acc 0000320193-25-000079, FY ended 2025-09-27
- Income statement page: R3.htm ("CONSOLIDATED STATEMENTS OF OPERATIONS")
- Net sales: $416,161M · Net income: $112,010M · Diluted EPS: $7.46
- URL: https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/R3.htm

## Microsoft Corp — 10-K filed 2026-07-29, acc 0001193125-26-323660, FY ended 2026-06-30
- Income statement page: R2.htm ("INCOME STATEMENTS")
- Revenue: $331,839M · Net income: $133,749M · Diluted EPS: $17.95
- URL: https://www.sec.gov/Archives/edgar/data/789019/000119312526323660/R2.htm

## Route (verified working, all server-rendered, no JS needed)
1. /cgi-bin/browse-edgar?action=getcompany&company=<name>&type=10-K&count=5
2. Newest row → "Documents" → filing index page
3. Same folder → FilingSummary.xml → find income-statement Rn.htm (name varies)
4. Rn.htm is a small clean text table; read newest fiscal-year column

---

## Post-deploy finding (2026-08-02): SEC blocks datacenter IPs

Verified from production: SEC returns "Your Request Originates from an
Undeclared Automated Tool" for **every** endpoint (CGI browse-edgar,
data.sec.gov, EDGAR full-text UI, raw Archives) when requested from
Railway. Proven to be IP-level, not User-Agent-level: httpbin.org/user-agent
echoed our correctly-declared UA
(`Glassbox-Agent/1.0 (Jay Chak; contact: ...)`) from the same deploy, and
SEC still refused. The same route works fine from a residential IP.

**Resolution:** the financials showcase now sources stockanalysis.com,
whose figures were cross-checked against the SEC filings above and match
exactly:

| Company | FY | Revenue ($M) | Net income ($M) | EPS | SEC match |
|---|---|---|---|---|---|
| Apple | FY2025 (ends 2025-09-27) | 416,161 | 112,010 | 7.46 | exact |
| Microsoft | FY2026 (ends 2026-06-30) | 331,839 | 133,749 | 17.95 | exact |

Use these to verify any run of the "Compare company financials" preset.
Net margin check: Apple 112,010/416,161 = 26.9%; Microsoft
133,749/331,839 = 40.3%.

---

## Research brief (multi-site) — NVIDIA, recorded 2026-08-03

Two independent sources, both read by hand; they agree.

**Wikipedia** (https://en.wikipedia.org/wiki/Nvidia):
- Founded April 5, 1993, in Sunnyvale, California
- Headquarters: Santa Clara, California
- Founders: Jensen Huang, Chris Malachowsky, Curtis Priem
- Infobox financials: revenue US$215.9B (FY26), net income US$120.1B (FY26)

**stockanalysis.com** (https://stockanalysis.com/stocks/nvda/financials/):
- Latest completed FY = FY2026 (ended Jan 25, 2026)
- Revenue: $215,938M · Net income: $120,067M · EPS: 4.90

Cross-source check: both put FY2026 revenue at ~$215.9B and net income at
~$120.1B. A correct brief should note the two sources agree.
