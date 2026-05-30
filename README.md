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
