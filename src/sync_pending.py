from __future__ import annotations

from accountant import (
    mark_inbox_synced,
    pending_inbox,
    write_pending_xlsx,
    write_snapshot,
    PENDING_XLSX_PATH,
)
from import_transactions import export_wallet_balances, import_rows, init_driver, login, validate_xlsx


def main():
    pending = pending_inbox()
    driver = None
    try:
        driver = init_driver()
        print('Logging in')
        login(driver)
        print('Logging success')
        if pending:
            xlsx_path = write_pending_xlsx(pending, PENDING_XLSX_PATH)
            print(f'Importing {len(pending)} pending row(s) from {xlsx_path}')
            validate_xlsx(xlsx_path)
            import_rows(driver, str(xlsx_path))
            mark_inbox_synced([row['id'] for row in pending])
            print('Inbox rows marked synced')
        else:
            print('No pending inbox rows')
        wallets = export_wallet_balances(driver)
        snapshot = write_snapshot(wallets)
        print(f'Snapshot wrote {len(snapshot.get("wallets") or [])} wallet(s)')
    finally:
        if driver:
            driver.quit()


if __name__ == '__main__':
    main()
