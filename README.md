# Import transactions to Money Lover web

A Selenium script to import transactions from an Excel file into [Money Lover](https://web.moneylover.me/).

The script targets the **Vietnamese** web UI. Category names in Excel must match the category names shown in Money Lover.

## Requirements

- Python 3.10+
- Google Chrome
- A Money Lover account with **email/password** login (Google/Apple sign-in is not supported by this script)

## Prepare

1. Create `data/transactions.xlsx`. Each sheet name must be the **exact wallet name** in Money Lover.

   Example sheet name: `Tín Dụng Everyday`

2. Create a folder to store the Chrome session (keeps you logged in between runs):

   ```bash
   mkdir chromedata
   ```

3. Add transactions in each sheet with these columns:

   | Column | Description |
   |--------|-------------|
   | `Date` | Example: `31/12/2023` or `12-Jun-2022` |
   | `Category` | Format: `Expense\|CategoryName` or `Income\|CategoryName` |
   | `Note` | Short note for the transaction |
   | `Description` | Optional. Can match the bank statement |
   | `Change` or `Withdraw` or `Deposit` | Amount. `Change` can be positive or negative |

   **Category examples**

   ```
   Expense|Mua sắm
   Expense|Ăn uống
   Expense|Di chuyển
   Expense|Hoá đơn & Tiện ích
   Income|Lương
   ```

   The part after `|` must match a category name in Money Lover exactly. Supported Vietnamese categories are listed in `src/import_transactions.py` under `valid_categories`.

4. Do not put transfers into the sheets. Remember them separately — this script does not support transfers.

5. Configure environment variables:

   ```bash
   cp .env.example .env
   ```

   Edit `.env`:

   ```env
   MONEYLOVER_USER_NAME=your@email.com
   MONEYLOVER_PASSWORD=your_password
   CHROME_USER_DATA_DIR=./chromedata
   ENV=local
   ```

## Run locally

1. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Run the import from the project root:

   ```bash
   python src/import_transactions.py
   ```

3. Import transfers manually in Money Lover.

## Run with Docker

Does not work on Apple Silicon Macs.

```bash
docker-compose up -d
docker-compose exec selenium python src/import_transactions.py
```

Watch the browser inside the container: http://localhost:7900/?autoconnect=1&resize=scale&password=secret

## Troubleshooting

**`ModuleNotFoundError`** — activate the virtual environment and install dependencies:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

**`SessionNotCreatedException: Chrome instance exited`** — a previous Chrome session is still using the profile. Close any Chrome window opened by this script, then run again. The script will also try to clean up stale automation Chrome sessions automatically.

**Login timeout** — check `MONEYLOVER_USER_NAME` and `MONEYLOVER_PASSWORD` in `.env`.

**Invalid category** — make sure the category name in Excel matches Money Lover exactly, including accents and spacing.

**Invalid title** — use `Expense` or `Income` as the prefix in the `Category` column.

## Daily accountant

Spends live in the Notion database [Money Lover transactions](https://www.notion.so/8f8bce6b36944097b06cf5fb6ad6fbd0). Wallet balances stay in `data/wallet_snapshot.json` on this Mac.

1. Edit `data/accountant_config.yaml`: exact Money Lover wallet names for spending + banks A/B/C, optional `monthly_budget`, and `report_email_to`. `notion_database_id` is already set.
2. Copy mail secrets into `.env` (see `.env.example`): `REPORT_EMAIL_TO` plus either `RESEND_API_KEY` or SMTP settings.
3. Notion API for Mac sync: create an internal integration at https://www.notion.so/my-integrations, share **Money Lover transactions** with it, put `NOTION_TOKEN` in `.env` and in Cursor Automation secrets.

### iOS Shortcut → webhook

1. Save Cursor Automation **Money Lover — ingest spend** (webhook, repo `7on9/moneylover-import`). Enable the Notion MCP (`notion`).
2. Copy the webhook URL and auth header from the Automations editor.
3. In the Shortcuts app:

   - **Ask for Input** (Number) — amount.
   - **Ask for Input** (Text) — note. Optional: another Ask for category.
   - **Get Contents of URL**: Method `POST`, URL = webhook URL, Headers = the auth header from the editor, body JSON below.
   - **Show Notification** — `Queued for Money Lover`.

```json
{
  "amount": 45000,
  "note": "Cafe Highlands",
  "wallet": "Tín Dụng Everyday",
  "category": "Ăn uống",
  "type": "expense",
  "date": "2026-09-18"
}
```

Use Shortcut variables for `amount` and `note`. Omit `category` to let ingest suggest one. Omit `date` to use today (Vietnam). Omit `wallet` to use `default_wallet`. `type` is `expense` or `income`.

The webhook agent runs `python src/ingest_spend.py '<json>'` (needs `NOTION_TOKEN`). That creates a Notion row with `Status=pending`. It does **not** open Money Lover. Do not commit jsonl.

### Local Mac sync (writes into Money Lover)

Cloud agents cannot use your Chrome profile. On this Mac, after new iOS spends (and before 21:00 if you want fresh balances in the email):

```bash
source .venv/bin/activate
python src/sync_pending.py
```

Or: `scripts/sync-pending.sh`

That imports Notion rows with `Status=pending`, marks them `synced`, then refreshes `data/wallet_snapshot.json`.

Optional launchd (20:00 local, before the 21:00 email). The plist already uses this Mac's project path. The Mac must be awake at 20:00:

```bash
cp scripts/com.moneylover.sync-pending.plist.example ~/Library/LaunchAgents/com.moneylover.sync-pending.plist
launchctl load ~/Library/LaunchAgents/com.moneylover.sync-pending.plist
```

### End-of-day email

Cursor Automation **Daily accountant — EOD report** runs at 21:00 Vietnam (`0 14 * * *` UTC). Enable the Notion MCP and set `NOTION_TOKEN` plus mail secrets. It should execute:

```bash
python src/send_report_email.py
```

Preview without sending: `python -c "from accountant import build_report; print(build_report())"` from `src/`.

Report shape:

```text
Today: … | This week: … | This month: … | Balance left: …
Saving plan: Bank A … | Bank B … | Bank C … | Saved …
Investigate:
  - …
```

