---
name: daily-accountant
description: Ingest iOS spend webhooks into the Notion Money Lover transactions database, categorize spends, sync pending rows into Money Lover, and write the end-of-day spend/savings report. Use when ingesting a spend, running the daily accountant, building the EOD email, or categorizing Money Lover transactions.
---

# Daily accountant

Work from `moneylover-import/`. Spends live in Notion database **Money Lover transactions** (`notion_database_id` in `data/accountant_config.yaml`). Do not write `data/inbox.jsonl` or `data/ledger.jsonl`.

## Ingest (webhook)

1. Parse the request JSON body (unwrap envelopes until you have the spend object).
2. Read the note the user sent and decide the category for them. Prefer an exact name from `src/categories.py` `VALID_CATEGORIES`. If the payload already has a valid `category`, keep it. Otherwise choose from the note (keywords in `CATEGORY_KEYWORDS` are a starting point; use judgment when they are weak). Always pass `category` into `ingest_spend.py` so Notion stores your decision.
3. Run (requires `NOTION_TOKEN`):

```bash
python src/ingest_spend.py '{"amount":45000,"note":"Cafe Highlands","wallet":"Tín Dụng Everyday","category":"Ăn uống","type":"expense","date":"2026-09-18"}'
```

4. Confirm a new Notion row with `Status=pending`. Do not commit jsonl.
5. Print the ingested row (include Notion URL if present). Do not run Selenium in the cloud.

`date` is optional (defaults to today Vietnam). `type` defaults to `expense`. Wallet defaults to `default_wallet` in `data/accountant_config.yaml`. Do not omit `category` after step 2.

If the Python write fails, you may create the same row with Notion MCP in database **Money Lover transactions**. Properties: Name (note), Amount, Date, Type (`expense`/`income`), Category, Category suggested, Wallet, Status=`pending`, Ingested at, Spend ID (uuid).

### Categorize

- You have to read the note the user sent and decide the category for them.
- If `category` matches a name in `src/categories.py` `VALID_CATEGORIES`, keep it.
- Else pick the best match from the note against `VALID_CATEGORIES` (keyword helpers in `CATEGORY_KEYWORDS` are optional).
- Always include that `category` in the JSON passed to `ingest_spend.py`.
- Write `Expense|Name` or `Income|Name` only when building the Excel import.

## Local Money Lover sync (Mac only)

On this Mac only. Never run Selenium, Chrome, or `python src/sync_pending.py` from a cloud automation. Webhook and EOD automations stay Notion + email only.

When the user says sync pending / import Notion to Money Lover, run:

```bash
cd /Users/longnguyen/source/my/money_lover_import/moneylover-import
source .venv/bin/activate
python src/sync_pending.py
```

Close other Chrome windows that use `chromedata` first. Needs `NOTION_TOKEN`, `ENV=local`, and `CHROME_USER_DATA_DIR=./chromedata`. Imports Notion `Status=pending` rows, marks them `synced`, refreshes `data/wallet_snapshot.json`.

Background schedule is launchd at 20:00 (`scripts/com.moneylover.sync-pending.plist.example`), not a Cursor cloud automation. A `/loop` only runs while this chat stays open.

## EOD report (cron ~21:00 Vietnam)

1. Prefer `python src/send_report_email.py` (reads Notion + `data/wallet_snapshot.json`, archives `data/reports/YYYY-MM-DD.md`, emails).
2. Keep this exact shape:

```text
Today: … | This week: … | This month: … | Balance left: …
Saving plan: Bank A … | Bank B … | Bank C … | Saved …
Investigate:
  - …
```

3. Commit the report archive if written. Do not commit jsonl.
4. Secrets: `NOTION_TOKEN`, `REPORT_EMAIL_TO`, plus `RESEND_API_KEY` or `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD`. Fail closed if they are missing.

### Investigate checklist (2–5 bullets)

- Inbox backlog not synced to Money Lover (`Status=pending`)
- Wallet snapshot missing or older than `stale_snapshot_hours`
- Month spend ahead of `monthly_budget` pace
- Today rows that used a suggested category
- Large outliers (about 1,000,000 VND or 3x today's median)

Edit `saving_wallets.bank_a/b/c` to the exact Money Lover wallet names before trusting savings lines.
