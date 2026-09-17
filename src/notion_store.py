from __future__ import annotations

import os

from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

PAGE_SIZE = 100


def notion_client():
    token = os.environ.get('NOTION_TOKEN')
    if not token:
        raise SystemExit(
            'NOTION_TOKEN is not set. Create a Notion internal integration, '
            'share Money Lover transactions with it, and put the token in .env.'
        )
    return Client(auth=token)


def database_id(config):
    db_id = os.environ.get('NOTION_DATABASE_ID') or config.get('notion_database_id') or ''
    db_id = str(db_id).strip()
    if not db_id:
        raise SystemExit('Set notion_database_id in data/accountant_config.yaml or NOTION_DATABASE_ID')
    return db_id


def _plain(rich):
    return ''.join(part.get('plain_text') or '' for part in (rich or []))


def _title_text(prop):
    return _plain((prop or {}).get('title'))


def _select_name(prop):
    select = (prop or {}).get('select') or {}
    return select.get('name') or ''


def page_to_row(page):
    props = page.get('properties') or {}
    date_start = ((props.get('Date') or {}).get('date') or {}).get('start') or ''
    ingested = ((props.get('Ingested at') or {}).get('date') or {}).get('start') or ''
    amount = (props.get('Amount') or {}).get('number')
    return {
        'page_id': page['id'],
        'id': _plain((props.get('Spend ID') or {}).get('rich_text')) or page['id'],
        'amount': int(amount or 0),
        'note': _title_text(props.get('Name')),
        'wallet': _plain((props.get('Wallet') or {}).get('rich_text')),
        'category': _plain((props.get('Category') or {}).get('rich_text')),
        'category_suggested': bool((props.get('Category suggested') or {}).get('checkbox')),
        'type': _select_name(props.get('Type')) or 'expense',
        'date': date_start[:10],
        'status': _select_name(props.get('Status')) or 'pending',
        'ingested_at': ingested,
        'url': page.get('url') or '',
    }


def _query(client, db_id, filter_obj=None):
    rows = []
    cursor = None
    while True:
        payload = {'database_id': db_id, 'page_size': PAGE_SIZE}
        if filter_obj:
            payload['filter'] = filter_obj
        if cursor:
            payload['start_cursor'] = cursor
        result = client.databases.query(**payload)
        for page in result.get('results') or []:
            rows.append(page_to_row(page))
        if not result.get('has_more'):
            break
        cursor = result.get('next_cursor')
    return rows


def create_spend(row, config):
    client = notion_client()
    db_id = database_id(config)
    title = (row.get('note') or f"{row['amount']} {row['category']}")[:2000]
    ingested = row.get('ingested_at') or row['date']
    page = client.pages.create(
        parent={'database_id': db_id},
        properties={
            'Name': {'title': [{'text': {'content': title}}]},
            'Amount': {'number': int(row['amount'])},
            'Date': {'date': {'start': row['date']}},
            'Type': {'select': {'name': row['type']}},
            'Category': {'rich_text': [{'text': {'content': row['category']}}]},
            'Category suggested': {'checkbox': bool(row.get('category_suggested'))},
            'Wallet': {'rich_text': [{'text': {'content': row['wallet']}}]},
            'Status': {'select': {'name': row.get('status') or 'pending'}},
            'Ingested at': {'date': {'start': ingested}},
            'Spend ID': {'rich_text': [{'text': {'content': row['id']}}]},
        },
    )
    converted = page_to_row(page)
    row['page_id'] = converted['page_id']
    row['url'] = converted.get('url') or ''
    return row


def list_pending(config):
    return _query(
        notion_client(),
        database_id(config),
        {'property': 'Status', 'select': {'equals': 'pending'}},
    )


def list_expenses_since(config, start_date):
    return _query(
        notion_client(),
        database_id(config),
        {
            'and': [
                {'property': 'Type', 'select': {'equals': 'expense'}},
                {'property': 'Date', 'date': {'on_or_after': start_date}},
            ]
        },
    )


def list_all_since(config, start_date):
    return _query(
        notion_client(),
        database_id(config),
        {'property': 'Date', 'date': {'on_or_after': start_date}},
    )


def mark_pages_synced(page_ids):
    client = notion_client()
    for page_id in page_ids:
        client.pages.update(
            page_id=page_id,
            properties={'Status': {'select': {'name': 'synced'}}},
        )
