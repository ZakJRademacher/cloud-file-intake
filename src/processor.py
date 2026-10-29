"""Pure CSV validation and transformation. No network or filesystem access."""
from collections import defaultdict
import csv
from datetime import date
import io
import re

CONTRACT_VERSION = 'sales-v1'
MAX_BYTES = 1_000_000
MAX_ROWS = 5_000
HEADERS = ['record_id', 'sale_date', 'category', 'quantity', 'unit_price_cents']
ALIASES = {'line_id': 'record_id', 'id': 'record_id', 'date': 'sale_date',
           'product_category': 'category', 'qty': 'quantity', 'price_cents': 'unit_price_cents'}
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z')
CATEGORY = re.compile(r'[A-Za-z][A-Za-z0-9 &/().-]{0,79}\Z')
INTEGER = re.compile(r'[+-]?\d{1,9}\Z', re.ASCII)


class InputError(ValueError):
    """A permanent file-contract error; the original can be quarantined."""


def csv_bytes(headers, rows):
    out = io.StringIO(newline='')
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(headers)
    # Review exports contain untrusted rejected text. Keep it inert in spreadsheets.
    # Actual numeric values in accepted outputs remain numeric; raw bytes stay unchanged.
    writer.writerows([["'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@'))
                      else value for value in row] for row in rows])
    return out.getvalue().encode('utf-8')


def parse(data):
    if len(data) > MAX_BYTES:
        raise InputError('file_too_large: maximum size is 1,000,000 bytes')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeError as error:
        raise InputError('invalid_encoding: use UTF-8 CSV') from error
    if '\x00' in text:
        raise InputError('invalid_encoding: NUL bytes are not accepted')
    try:
        reader = csv.reader(io.StringIO(text, newline=''), strict=True)
        header = next(reader, None)
        if not header:
            raise InputError('missing_header: the file is empty')
        normalized = [ALIASES.get(x.strip().lower(), x.strip().lower()) for x in header]
        if len(set(normalized)) != len(normalized) or set(normalized) != set(HEADERS):
            raise InputError('invalid_header: exactly one of each required column is needed')
        positions = [normalized.index(h) for h in HEADERS]
        rows = []
        for cells in reader:
            if not cells:  # Empty physical lines are not data records.
                continue
            if len(cells) != len(header):
                raise InputError('invalid_row_width: every data row must have all five columns')
            if len(rows) >= MAX_ROWS:
                raise InputError('too_many_rows: maximum is 5,000 data rows')
            rows.append([cells[i].strip() for i in positions])
        return rows
    except csv.Error as error:
        raise InputError('invalid_csv: check quoting and field lengths') from error


def row_reason(row, conflicts):
    record_id, day, category, quantity, price = row
    if not ID.fullmatch(record_id):
        return 'invalid_record_id'
    if record_id in conflicts:
        return 'conflicting_record_id'
    try:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day, re.ASCII):
            return 'invalid_date'
        date.fromisoformat(day)
    except ValueError:
        return 'invalid_date'
    if not CATEGORY.fullmatch(category):
        return 'invalid_category'
    if not INTEGER.fullmatch(quantity) or abs(int(quantity)) > 1_000_000:
        return 'invalid_quantity'
    if not INTEGER.fullmatch(price) or not 0 <= int(price) <= 100_000_000:
        return 'invalid_unit_price'
    return None


def transform(data):
    """Return deterministic artifacts and reconciled counts for one complete file.

    IDs remain text; quantities and integer-cent prices are validated explicitly.
    Conflicts are identified across the whole file before accepting any record.
    """
    rows = parse(data)
    signatures = defaultdict(set)
    for row in rows:
        signatures[row[0]].add(tuple(row))
    conflicts = {key for key, values in signatures.items() if len(values) > 1}
    accepted, review, skipped, seen = [], [], [], set()
    totals = defaultdict(lambda: [0, 0])
    for number, row in enumerate(rows, start=1):
        reason = row_reason(row, conflicts)
        if reason:
            review.append([number, *row, reason])
        elif row[0] in seen:
            skipped.append([number, *row, 'exact_repeat'])
        else:
            seen.add(row[0])
            record_id, day, category, quantity, price = row
            quantity, price = int(quantity), int(price)
            amount = quantity * price
            accepted.append([number, record_id, day, category, quantity, price, amount])
            totals[category][0] += amount
            totals[category][1] += 1
    net = sum(row[-1] for row in accepted)
    counts = {'input_rows': len(rows), 'accepted_rows': len(accepted),
              'review_rows': len(review), 'skipped_rows': len(skipped), 'net_cents': net}
    assert counts['input_rows'] == counts['accepted_rows'] + counts['review_rows'] + counts['skipped_rows']
    assert net == sum(values[0] for values in totals.values())
    return counts, {
        'accepted.csv': csv_bytes(['source_row', *HEADERS, 'amount_cents'], accepted),
        'needs_review.csv': csv_bytes(['source_row', *HEADERS, 'reason'], review),
        'skipped.csv': csv_bytes(['source_row', *HEADERS, 'reason'], skipped),
        'summary.csv': csv_bytes(['category', 'net_cents', 'record_count'],
                                 [[key, *totals[key]] for key in sorted(totals)]),
    }
