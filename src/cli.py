"""Run the same processor locally, without AWS credentials or dependencies."""
import argparse
import json
from pathlib import Path
from .jobs import digest, run_job
from .processor import MAX_BYTES
from .storage import LocalStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--store', type=Path, default=Path('local-data'))
    args = parser.parse_args()
    with args.file.open('rb') as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        parser.error('The demo accepts files up to 1,000,000 bytes; the original was not copied.')
    store = LocalStore(args.store)
    raw_key = f'raw/{digest(data)}.csv'
    store.put(raw_key, data, 'text/csv')
    result = run_job(store, data, {'mode': 'local', 'filename': args.file.name, 'raw_key': raw_key})
    print(json.dumps(result, indent=2))
    return 2 if result['status'] == 'quarantined' else 0


if __name__ == '__main__':
    raise SystemExit(main())
