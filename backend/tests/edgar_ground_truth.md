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
