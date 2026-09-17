---
name: daily-accountant
description: Ingest iOS spend webhooks into the Money Lover ledger, categorize transactions, sync pending rows, and write the end-of-day spend/savings report plus investigate plan. Use when ingesting a spend, running the daily accountant, building the EOD email, or categorizing Money Lover transactions.
---

# Daily accountant

Work from `moneylover-import/`. Keep this repo private — `data/ledger.jsonl` and `data/inbox.jsonl` are personal finance.

## Ingest (webhook)

1. Parse the request JSON body (unwrap envelopes until you have the spend object).
2. Run:

```bash
python src/ingest_spend.py '{"amount":45000,"note":"Cafe Highlands","wallet":"Tín Dụng Everyday","category":"Ăn uống","type":"expense","date":"2026-09-18"}'
```

3. Commit `data/inbox.jsonl` and `data/ledger.jsonl`.
4. Print the ingested row. Do not run Selenium in the cloud.

`category` and `date` are optional. `type` defaults to `expense`. Wallet defaults to `default_wallet` in `data/accountant_config.yaml`.

### Categorize

- If `category` matches a name in `src/categories.py` `VALID_CATEGORIES`, keep it.
- Else pick from the note using `suggest_category` (already done by `ingest_spend.py`).
- Write `Expense|Name` or `Income|Name` only when building the Excel import. Ledger stores `category` and `type` separately.

## Local Money Lover sync (Mac only)

```bash
python src/sync_pending.py
```

Imports pending inbox rows via Selenium, marks them synced, refreshes `data/wallet_snapshot.json`. Cloud agents cannot do this.

## EOD report (cron ~21:00 Vietnam)

1. Read `data/ledger.jsonl`, `data/wallet_snapshot.json`, `data/accountant_config.yaml`.
2. Prefer `python src/send_report_email.py` (archives `data/reports/YYYY-MM-DD.md` and emails).
3. If you edit the investigate bullets, keep this exact shape:

```text
Today: … | This week: … | This month: … | Balance left: …
Saving plan: Bank A … | Bank B … | Bank C … | Saved …
Investigate:
  - …
```

4. Commit the archive and any ledger/inbox/snapshot updates.
5. Mail secrets: `REPORT_EMAIL_TO` plus `RESEND_API_KEY` or `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD`. Fail closed if they are missing.

### Investigate checklist (2–5 bullets)

- Inbox backlog not synced to Money Lover
- Wallet snapshot missing or older than `stale_snapshot_hours`
- Month spend ahead of `monthly_budget` pace
- Today rows that used a suggested category
- Large outliers (about 1,000,000 VND or 3x today's median)

Edit `saving_wallets.bank_a/b/c` to the exact Money Lover wallet names before trusting savings lines.
