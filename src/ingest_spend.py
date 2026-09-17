from __future__ import annotations

import json
import sys

from accountant import ingest_spend


def load_payload(argv):
    if len(argv) > 1:
        return json.loads(argv[1])
    raw = sys.stdin.read().strip()
    if not raw:
        raise SystemExit('Pass JSON as the first argument or on stdin')
    return json.loads(raw)


def main():
    row = ingest_spend(load_payload(sys.argv))
    print(json.dumps(row, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
