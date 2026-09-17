from __future__ import annotations

import json
import os
import re
import uuid
from calendar import monthrange
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from openpyxl import Workbook

from categories import CATEGORY_KEYWORDS, VALID_CATEGORIES

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'data'
CONFIG_PATH = DATA_DIR / 'accountant_config.yaml'
INBOX_PATH = DATA_DIR / 'inbox.jsonl'
LEDGER_PATH = DATA_DIR / 'ledger.jsonl'
SNAPSHOT_PATH = DATA_DIR / 'wallet_snapshot.json'
REPORTS_DIR = DATA_DIR / 'reports'
PENDING_XLSX_PATH = DATA_DIR / 'pending_import.xlsx'

DEFAULT_CONFIG = {
    'timezone': 'Asia/Ho_Chi_Minh',
    'report_email_to': '',
    'spending_wallet': 'Tín Dụng Everyday',
    'saving_wallets': {
        'bank_a': 'Bank A',
        'bank_b': 'Bank B',
        'bank_c': 'Bank C',
    },
    'monthly_budget': 0,
    'default_wallet': 'Tín Dụng Everyday',
    'stale_snapshot_hours': 24,
}


def now_vn(tz_name=None):
    tz = ZoneInfo(tz_name or load_config()['timezone'])
    return datetime.now(tz)


def load_config():
    if not CONFIG_PATH.exists():
        return dict(DEFAULT_CONFIG)
    with CONFIG_PATH.open(encoding='utf-8') as fh:
        loaded = yaml.safe_load(fh) or {}
    config = dict(DEFAULT_CONFIG)
    config.update(loaded)
    saving = dict(DEFAULT_CONFIG['saving_wallets'])
    saving.update(loaded.get('saving_wallets') or {})
    config['saving_wallets'] = saving
    return config


def read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows)
    path.write_text(text, encoding='utf-8')


def append_jsonl(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + '\n')


def parse_vnd(text):
    if text is None:
        return 0
    if isinstance(text, (int, float)):
        return int(abs(text))
    cleaned = re.sub(r'[^\d,.\-]', '', str(text))
    if not cleaned or cleaned in '-.,':
        return 0
    if cleaned.count('.') > 1 and ',' not in cleaned:
        cleaned = cleaned.replace('.', '')
    elif cleaned.count(',') > 1:
        cleaned = cleaned.replace(',', '')
    else:
        cleaned = cleaned.replace(',', '')
    return int(abs(float(cleaned)))


def format_vnd(amount):
    return f'{int(amount):,} VND'


def normalize_category(name):
    if not name:
        return None
    name = str(name).strip()
    if name in VALID_CATEGORIES:
        return name
    lowered = name.casefold()
    for category in VALID_CATEGORIES:
        if category.casefold() == lowered:
            return category
    return None


def suggest_category(note, provided=None):
    matched = normalize_category(provided)
    if matched:
        return matched, False
    haystack = (note or '').casefold()
    for keywords, category in CATEGORY_KEYWORDS:
        for keyword in keywords:
            if keyword.casefold() in haystack:
                return category, True
    return 'Các chi phí khác', True


def parse_date_value(value, today):
    if not value:
        return today.strftime('%Y-%m-%d')
    text = str(value).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(text, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    raise ValueError(f'Invalid date: {value}')


def normalize_spend(payload, config=None):
    config = config or load_config()
    today = now_vn(config['timezone']).date()
    if 'amount' not in payload:
        raise ValueError('amount is required')
    amount = parse_vnd(payload['amount'])
    if amount == 0:
        raise ValueError('amount must be greater than 0')
    note = str(payload.get('note') or '').strip()
    spend_type = str(payload.get('type') or 'expense').strip().lower()
    if spend_type not in ('expense', 'income'):
        raise ValueError('type must be expense or income')
    category, suggested = suggest_category(note, payload.get('category'))
    wallet = str(payload.get('wallet') or config['default_wallet']).strip()
    if not wallet:
        raise ValueError('wallet is required')
    row = {
        'id': payload.get('id') or str(uuid.uuid4()),
        'amount': amount,
        'note': note,
        'wallet': wallet,
        'category': category,
        'category_suggested': suggested,
        'type': spend_type,
        'date': parse_date_value(payload.get('date'), today),
        'status': 'pending',
        'ingested_at': now_vn(config['timezone']).isoformat(timespec='seconds'),
    }
    return row


def ingest_spend(payload, config=None):
    row = normalize_spend(payload, config)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    append_jsonl(INBOX_PATH, row)
    append_jsonl(LEDGER_PATH, row)
    return row


def pending_inbox():
    return [row for row in read_jsonl(INBOX_PATH) if row.get('status') == 'pending']


def write_pending_xlsx(rows, path=PENDING_XLSX_PATH):
    if not rows:
        return None
    by_wallet = {}
    for row in rows:
        by_wallet.setdefault(row['wallet'], []).append(row)
    wb = Workbook()
    first = True
    for wallet, items in by_wallet.items():
        ws = wb.active if first else wb.create_sheet()
        first = False
        ws.title = wallet[:31]
        ws.append(['Date', 'Category', 'Note', 'Description', 'Change'])
        for item in items:
            kind = 'Income' if item.get('type') == 'income' else 'Expense'
            date = datetime.strptime(item['date'], '%Y-%m-%d').strftime('%d/%m/%Y')
            ws.append([date, f'{kind}|{item["category"]}', item.get('note') or '', '', item['amount']])
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def mark_inbox_synced(ids, tz_name=None):
    synced_at = now_vn(tz_name).isoformat(timespec='seconds')
    id_set = set(ids)
    inbox = read_jsonl(INBOX_PATH)
    for row in inbox:
        if row.get('id') in id_set:
            row['status'] = 'synced'
            row['synced_at'] = synced_at
    write_jsonl(INBOX_PATH, inbox)
    ledger = read_jsonl(LEDGER_PATH)
    for row in ledger:
        if row.get('id') in id_set:
            row['status'] = 'synced'
            row['synced_at'] = synced_at
    write_jsonl(LEDGER_PATH, ledger)


def write_snapshot(wallets, extra=None):
    payload = {
        'synced_at': now_vn().isoformat(timespec='seconds'),
        'wallets': wallets,
    }
    if extra:
        payload.update(extra)
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return payload


def load_snapshot():
    if not SNAPSHOT_PATH.exists():
        return None
    return json.loads(SNAPSHOT_PATH.read_text(encoding='utf-8'))


def wallet_balance(snapshot, name):
    if not snapshot:
        return None
    for wallet in snapshot.get('wallets') or []:
        if wallet.get('name') == name:
            return wallet.get('balance')
    return None


def period_bounds(when):
    today = when.date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    return today, week_start, month_start


def expense_total(rows, start_date, end_date):
    total = 0
    for row in rows:
        if row.get('type') != 'expense':
            continue
        if start_date <= row['date'] <= end_date:
            total += int(row['amount'])
    return total


def snapshot_age_hours(snapshot, when):
    if not snapshot or not snapshot.get('synced_at'):
        return None
    synced = datetime.fromisoformat(snapshot['synced_at'])
    if synced.tzinfo is None:
        synced = synced.replace(tzinfo=when.tzinfo)
    return (when - synced).total_seconds() / 3600


def investigate_plan(ledger, snapshot, config, when):
    today, week_start, month_start = period_bounds(when)
    today_s = today.strftime('%Y-%m-%d')
    month_end = today.strftime('%Y-%m-%d')
    bullets = []
    pending = [row for row in read_jsonl(INBOX_PATH) if row.get('status') == 'pending']
    if pending:
        bullets.append(f'{len(pending)} inbox item(s) not yet synced to Money Lover — run python src/sync_pending.py')
    age = snapshot_age_hours(snapshot, when)
    stale_after = float(config.get('stale_snapshot_hours') or 24)
    if not snapshot or not snapshot.get('synced_at'):
        bullets.append('No wallet snapshot yet — run python src/sync_pending.py so balance/savings are real Money Lover figures')
    elif age is not None and age > stale_after:
        bullets.append(f'Wallet snapshot is {age:.1f}h old — run python src/sync_pending.py before trusting balances')
    month_spent = expense_total(ledger, month_start.strftime('%Y-%m-%d'), month_end)
    budget = float(config.get('monthly_budget') or 0)
    if budget > 0:
        days_in_month = monthrange(today.year, today.month)[1]
        expected = budget * (today.day / days_in_month)
        if month_spent > expected:
            bullets.append(
                f'Month spend {format_vnd(month_spent)} is ahead of pace vs budget {format_vnd(budget)} '
                f'(expected ~{format_vnd(expected)} by day {today.day})'
            )
    suggested = [row for row in ledger if row.get('date') == today_s and row.get('category_suggested')]
    if suggested:
        notes = ', '.join((row.get('note') or row['category']) for row in suggested[:3])
        bullets.append(f'{len(suggested)} today item(s) used a suggested category — check: {notes}')
    today_rows = [row for row in ledger if row.get('date') == today_s and row.get('type') == 'expense']
    if len(today_rows) >= 1:
        amounts = sorted(int(row['amount']) for row in today_rows)
        median = amounts[len(amounts) // 2]
        outliers = [row for row in today_rows if int(row['amount']) >= max(1_000_000, median * 3 if median else 1_000_000)]
        if outliers:
            parts = [f"{row.get('note') or row['category']} {format_vnd(row['amount'])}" for row in outliers[:3]]
            bullets.append('Large today outlier(s): ' + '; '.join(parts))
    if not bullets:
        bullets.append('No issues flagged — skim categories and confirm savings wallets still match Money Lover names')
    return bullets[:5]


def build_report(config=None, when=None):
    config = config or load_config()
    when = when or now_vn(config['timezone'])
    ledger = read_jsonl(LEDGER_PATH)
    snapshot = load_snapshot()
    today, week_start, month_start = period_bounds(when)
    today_s = today.strftime('%Y-%m-%d')
    week_s = week_start.strftime('%Y-%m-%d')
    month_s = month_start.strftime('%Y-%m-%d')
    today_total = expense_total(ledger, today_s, today_s)
    week_total = expense_total(ledger, week_s, today_s)
    month_total = expense_total(ledger, month_s, today_s)
    spending_balance = wallet_balance(snapshot, config['spending_wallet'])
    if spending_balance is None:
        balance_text = 'n/a (run sync)'
    else:
        balance_text = format_vnd(spending_balance)
    saving = config['saving_wallets']
    bank_values = []
    saved = 0
    missing = False
    for key, label in (('bank_a', 'Bank A'), ('bank_b', 'Bank B'), ('bank_c', 'Bank C')):
        name = saving.get(key)
        value = wallet_balance(snapshot, name)
        if value is None:
            missing = True
            bank_values.append(f'{label} n/a')
        else:
            saved += int(value)
            bank_values.append(f'{label} {format_vnd(value)}')
    saved_text = 'n/a (run sync)' if missing and saved == 0 else format_vnd(saved)
    bullets = investigate_plan(ledger, snapshot, config, when)
    body = (
        f'Today: {format_vnd(today_total)} | This week: {format_vnd(week_total)} | '
        f'This month: {format_vnd(month_total)} | Balance left: {balance_text}\n'
        f'Saving plan: {" | ".join(bank_values)} | Saved {saved_text}\n'
        'Investigate:\n'
        + '\n'.join(f'  - {bullet}' for bullet in bullets)
    )
    return body


def archive_report(body, when=None):
    when = when or now_vn()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f'{when.date().isoformat()}.md'
    path.write_text(body + '\n', encoding='utf-8')
    return path


def report_email_to(config=None):
    config = config or load_config()
    return os.environ.get('REPORT_EMAIL_TO') or config.get('report_email_to') or ''
