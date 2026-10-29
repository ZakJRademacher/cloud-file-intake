"""Domain-neutral CSV consolidation and validation with explicit, portable profiles."""
import csv
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import io
import json
import re

ENGINE_VERSION = 'profiles-v1'
MAX_FILE_BYTES = 5_000_000
MAX_TOTAL_BYTES = 20_000_000
MAX_FILES = 20
MAX_ROWS = 50_000
DATE_FORMATS = {'YYYY-MM-DD': '%Y-%m-%d', 'MM/DD/YYYY': '%m/%d/%Y',
                'DD/MM/YYYY': '%d/%m/%Y', 'M/D/YYYY': '%m/%d/%Y', 'D/M/YYYY': '%d/%m/%Y'}
FIELD_ID = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,63}\Z')


class ProfileError(ValueError):
    pass


def canonical_json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def header_key(value):
    return re.sub(r'[ _-]', '', value.strip().casefold())


def decimal_bound(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or abs(number) > Decimal('1e24'):
            raise ValueError()
        return number
    except (ValueError, InvalidOperation):
        raise ProfileError('Numeric bounds must be finite numbers with magnitude at most 10^24.')


def validate_profile(value):
    if not isinstance(value, dict) or value.get('version') != 1:
        raise ProfileError('Use a version 1 profile object.')
    profile = json.loads(canonical_json(value))
    if not isinstance(profile.get('name'), str) or not 1 <= len(profile['name'].strip()) <= 100:
        raise ProfileError('Give the profile a name of 1–100 characters.')
    profile['name'] = profile['name'].strip()
    columns = profile.get('columns')
    if not isinstance(columns, list) or not 1 <= len(columns) <= 80:
        raise ProfileError('Define 1–80 output columns.')
    ids = []
    for column in columns:
        if not isinstance(column, dict) or not FIELD_ID.fullmatch(str(column.get('id', ''))):
            raise ProfileError('Field names must start with a letter and contain letters, numbers or underscores (up to 64 characters).')
        name = column['id']; ids.append(name)
        if name.startswith('__') or column.get('type') not in ['text', 'integer', 'decimal', 'date']:
            raise ProfileError(f'{name}: choose text, integer, decimal or date.')
        if not isinstance(column.get('required', False), bool):
            raise ProfileError(f'{name}: required must be true or false.')
        if column.get('type') == 'decimal':
            scale = column.get('scale', 4)
            if type(scale) is not int or not 0 <= scale <= 12:
                raise ProfileError(f'{name}: decimal places must be between 0 and 12.')
            column['scale'] = scale
        for bound in ['min', 'max']:
            if column.get(bound) not in [None, '']:
                if column['type'] not in ['integer', 'decimal']:
                    raise ProfileError(f'{name}: numeric bounds apply to number fields only.')
                decimal_bound(column[bound])
        if column.get('min') not in [None, ''] and column.get('max') not in [None, ''] and decimal_bound(column['min']) > decimal_bound(column['max']):
            raise ProfileError(f'{name}: minimum exceeds maximum.')
        allowed = column.get('allowed', [])
        if not isinstance(allowed, list) or len(allowed) > 500 or any(not isinstance(x, str) or len(x) > 300 for x in allowed):
            raise ProfileError(f'{name}: allowed values must be a list of text values.')
    if len(set(ids)) != len(ids):
        raise ProfileError('Output field names must be unique.')
    keys = profile.get('keys', [])
    if not isinstance(keys, list) or len(set(keys)) != len(keys) or any(x not in ids for x in keys):
        raise ProfileError('Key fields must refer to unique output field names.')
    if profile.get('duplicates') not in ['keys', 'exact', 'keep']:
        raise ProfileError('Choose key-based checks, exact-row duplicates or keep all rows.')
    if profile['duplicates'] == 'keys' and not keys:
        raise ProfileError('Choose at least one key field for key-based duplicate checks.')
    if profile.get('extra_columns', 'preserve') not in ['preserve', 'reject', 'ignore']:
        raise ProfileError('Choose preserve, reject or explicitly ignore extra columns.')
    totals = profile.get('totals', [])
    numeric = {c['id'] for c in columns if c['type'] in ['integer', 'decimal']}
    if not isinstance(totals, list) or len(set(totals)) != len(totals) or any(x not in numeric for x in totals):
        raise ProfileError('Totals must reference number fields.')
    formats = profile.get('formats', [])
    if not isinstance(formats, list) or not 1 <= len(formats) <= 50:
        raise ProfileError('Add 1–50 saved export formats.')
    names = []
    for fmt in formats:
        if not isinstance(fmt, dict) or not isinstance(fmt.get('name'), str) or not 1 <= len(fmt['name'].strip()) <= 100:
            raise ProfileError('Each export format needs a name.')
        names.append(fmt['name'])
        if fmt.get('delimiter') not in [',', ';', '\t', '|'] or fmt.get('encoding') not in ['utf-8-sig', 'cp1252']:
            raise ProfileError('Choose a supported delimiter and encoding for each format.')
        if fmt.get('date_format') not in DATE_FORMATS:
            raise ProfileError('Choose an explicit date format.')
        if fmt.get('decimal_mark', '.') not in ['.', ','] or fmt.get('group_mark', '') not in ['', ',', '.', ' ']:
            raise ProfileError('Choose supported decimal and thousands separators.')
        if fmt.get('decimal_mark', '.') == fmt.get('group_mark', ''):
            raise ProfileError('Decimal and thousands separators must differ.')
        mapping = fmt.get('mapping')
        if not isinstance(mapping, dict) or any(k not in ids or not isinstance(v, str) or len(v) > 300 for k, v in mapping.items()):
            raise ProfileError('Each format must map output fields to source headings.')
        mapped = [header_key(x) for x in mapping.values() if x]
        if len(mapped) != len(set(mapped)):
            raise ProfileError('A source column cannot feed two output fields.')
        required = {c['id'] for c in columns if c.get('required')}
        if profile['duplicates'] == 'keys': required.update(keys)
        if any(not mapping.get(k) for k in required):
            raise ProfileError(f'{fmt["name"]}: map all required and key fields.')
    if len(set(names)) != len(names):
        raise ProfileError('Export format names must be unique.')
    return profile


def read_file(data, fmt):
    if len(data) > MAX_FILE_BYTES:
        raise ProfileError('File exceeds 5 MB.')
    try:
        text = data.decode(fmt['encoding'])
        if '\x00' in text: raise ProfileError('NUL bytes are not supported.')
        reader = csv.reader(io.StringIO(text, newline=''), delimiter=fmt['delimiter'], strict=True)
        headers = next(reader, None)
        if not headers or len(headers) > 120 or any(not x.strip() or len(x) > 300 for x in headers):
            raise ProfileError('Use 1–120 nonempty source headings, up to 300 characters each.')
        if len(set(header_key(x) for x in headers)) != len(headers):
            raise ProfileError('Source headings are ambiguous after ignoring case, spaces, underscores and hyphens.')
        rows = []
        for number, cells in enumerate(reader, 2):
            if not cells: continue
            if len(cells) != len(headers):
                raise ProfileError(f'Wrong column count at CSV record {number}.')
            if len(rows) >= MAX_ROWS: raise ProfileError('File exceeds 50,000 data rows.')
            rows.append((number, dict(zip(headers, cells))))
        return headers, rows
    except (UnicodeError, csv.Error) as error:
        raise ProfileError('Cannot parse this file with the chosen encoding and delimiter: ' + str(error)) from error


def inspect_file(data, delimiter=',', encoding='utf-8-sig'):
    if delimiter not in [',', ';', '\t', '|'] or encoding not in ['utf-8-sig', 'cp1252']:
        raise ProfileError('Unsupported delimiter or encoding.')
    headers, rows = read_file(data, {'encoding': encoding, 'delimiter': delimiter})
    return {'headers': headers, 'rows': len(rows), 'preview': [raw for _, raw in rows[:5]],
            'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


def number_text(text, fmt):
    decimal_mark = fmt.get('decimal_mark', '.'); group = fmt.get('group_mark', '')
    digits = r'(?:\d+|\d{1,3}(?:' + re.escape(group) + r'\d{3})+)' if group else r'\d+'
    if not re.fullmatch(r'[+-]?' + digits + r'(?:' + re.escape(decimal_mark) + r'\d+)?', text, re.ASCII):
        raise ValueError('use the configured number separators, without currency symbols or exponents')
    return text.replace(group, '') .replace(decimal_mark, '.') if group else text.replace(decimal_mark, '.')


def normalize(text, column, fmt):
    text = text.strip(); kind = column['type']
    if not text:
        if column.get('required'): raise ValueError('required value is missing')
        return ''
    if len(text) > 10_000: raise ValueError('value exceeds 10,000 characters')
    if kind in ['integer', 'decimal']:
        parsed = number_text(text, fmt)
        value = Decimal(parsed)
        if not value.is_finite() or abs(value) > Decimal('1e24'): raise ValueError('number exceeds supported magnitude of 10^24')
        if kind == 'integer':
            if value != value.to_integral_value(): raise ValueError('whole number required')
            result = str(int(value))
        else:
            # Value-based scale: trailing zeros do not count as extra precision.
            with localcontext() as context:
                context.prec = 60
                if value != value.quantize(Decimal(1).scaleb(-column['scale'])):
                    raise ValueError(f'exceeds {column["scale"]} decimal places; no rounding applied')
            result = format(value, 'f')
            if '.' in result: result = result.rstrip('0').rstrip('.')
            if Decimal(result) == 0: result = '0'
        if column.get('min') not in [None, ''] and value < decimal_bound(column['min']): raise ValueError('below configured minimum')
        if column.get('max') not in [None, ''] and value > decimal_bound(column['max']): raise ValueError('above configured maximum')
    elif kind == 'date':
        date_format = fmt['date_format']
        regex = {'YYYY-MM-DD': r'\d{4}-\d{2}-\d{2}', 'MM/DD/YYYY': r'\d{2}/\d{2}/\d{4}',
                 'DD/MM/YYYY': r'\d{2}/\d{2}/\d{4}', 'M/D/YYYY': r'\d{1,2}/\d{1,2}/\d{4}', 'D/M/YYYY': r'\d{1,2}/\d{1,2}/\d{4}'}[date_format]
        if not re.fullmatch(regex, text, re.ASCII): raise ValueError('use date format ' + date_format)
        try: result = datetime.strptime(text, DATE_FORMATS[date_format]).date().isoformat()
        except ValueError as error: raise ValueError('invalid calendar date') from error
    else: result = text
    if column.get('allowed') and result not in column['allowed']:
        raise ValueError('not in configured allowed values')
    return result


def safe_csv(headers, rows, numeric=None):
    numeric = set(numeric or [])
    def safe(value, position):
        value = '' if value is None else str(value)
        if position not in numeric and value.lstrip().startswith(('=', '+', '-', '@')): return "'" + value
        return value
    stream = io.StringIO(newline=''); writer = csv.writer(stream, lineterminator='\n')
    writer.writerow([safe(x, -1) for x in headers])
    for row in rows: writer.writerow([safe(value, index) for index, value in enumerate(row)])
    return stream.getvalue().encode('utf-8')


def consolidate(profile, files):
    profile = validate_profile(profile)
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES: raise ProfileError('Choose 1–20 CSV files.')
    if sum(len(x['data']) for x in files) > MAX_TOTAL_BYTES: raise ProfileError('Batch exceeds 20 MB.')
    names = [f['name'] for f in files]
    if any(not isinstance(n, str) or not n or len(n) > 180 or '/' in n or '\\' in n for n in names):
        raise ProfileError('Use filenames of 1–180 characters without folder paths.')
    if len(set(names)) != len(names): raise ProfileError('Filenames must be unique within a batch. Rename files with matching names.')
    formats = {f['name']: f for f in profile['formats']}
    columns = profile['columns']; ids = [c['id'] for c in columns]
    records, issues, history, all_extras = [], [], [], set()
    for source in sorted(files, key=lambda f: f['name']):
        if source.get('format') not in formats: raise ProfileError(f'{source["name"]}: choose a saved export format.')
        fmt = formats[source['format']]
        item = {'file': source['name'], 'format': fmt['name'], 'sha256': hashlib.sha256(source['data']).hexdigest(),
                'bytes': len(source['data']), 'parsed_rows': None, 'accepted': 0, 'review': 0, 'skipped': 0, 'issue': ''}
        history.append(item)
        try:
            headers, rows = read_file(source['data'], fmt)
            by_key = {header_key(h): h for h in headers}
            mapping = {key: by_key.get(header_key(value)) for key, value in fmt['mapping'].items() if value}
            absent = [fmt['mapping'][key] for key, value in mapping.items() if value is None]
            if absent: raise ProfileError('Mapped source columns are missing: ' + ', '.join(absent))
            extras = sorted(set(headers) - set(mapping.values()))
            if extras and profile.get('extra_columns') == 'reject': raise ProfileError('Unmapped extra columns: ' + ', '.join(extras))
            if len(records) + len(rows) > MAX_ROWS: raise ProfileError('Combined parsed rows exceed 50,000.')
            if profile.get('extra_columns', 'preserve') == 'preserve': all_extras.update(extras)
            item['parsed_rows'] = len(rows)
            for number, raw in rows:
                values, errors = {}, []
                for column in columns:
                    key = column['id']; value = raw.get(mapping.get(key), '')
                    try: values[key] = normalize(value, column, fmt)
                    except ValueError as error: values[key] = value.strip(); errors.append(key + ': ' + str(error))
                if profile['duplicates'] == 'keys':
                    for key in profile['keys']:
                        if not values[key] and not any(e.startswith(key + ':') for e in errors): errors.append(key + ': key value is missing')
                extra_values = {h: raw[h] for h in extras} if profile.get('extra_columns', 'preserve') == 'preserve' else {}
                record = {'values': values, 'extra': extra_values, 'file': source['name'], 'record': number,
                          'raw': raw, 'errors': errors, 'status': None}
                records.append(record)
        except ProfileError as error:
            # Partial results remain visibly incomplete; do not pretend the failed file was empty.
            item['issue'] = str(error); issues.append([source['name'], str(error)])
    groups = defaultdict(list)
    for row in records:
        row['signature'] = canonical_json({'values': row['values'], 'extra': row['extra']})
        if profile['duplicates'] == 'keys' and all(row['values'][k] for k in profile['keys']):
            groups[tuple(row['values'][k] for k in profile['keys'])].append(row)
    conflicts = set()
    for key, group in groups.items():
        if len(group) > 1 and (len({r['signature'] for r in group}) > 1 or any(r['errors'] for r in group)): conflicts.add(key)
    seen = set()
    for row in records:
        key = tuple(row['values'][k] for k in profile['keys']) if profile['duplicates'] == 'keys' else row['signature']
        if profile['duplicates'] == 'keys' and key in conflicts: row['errors'].append('conflicting key: review every copy')
        if row['errors']: row['status'] = 'review'
        elif profile['duplicates'] != 'keep' and key in seen: row['status'] = 'skipped'; row['errors'].append('identical normalized repeat: retained first filename/record')
        else: row['status'] = 'accepted'; seen.add(key)
    by_file = {h['file']: h for h in history}
    for row in records: by_file[row['file']][row['status']] += 1
    extras = sorted(all_extras)
    output_headers = ['__source_file', '__source_record', *ids, *['extra:' + h for h in extras]]
    numeric = {1, *[i + 2 for i, c in enumerate(columns) if c['type'] in ['integer', 'decimal']]}
    def output(row): return [row['file'], row['record'], *[row['values'][k] for k in ids], *[row['extra'].get(k, '') for k in extras]]
    artifacts = {'accepted.csv': safe_csv(output_headers, [output(r) for r in records if r['status'] == 'accepted'], numeric)}
    for disposition, filename in [('review', 'needs_review.csv'), ('skipped', 'skipped.csv')]:
        artifacts[filename] = safe_csv([*output_headers, '__reasons', '__original_record_json'],
            [[*output(r), '; '.join(r['errors']), json.dumps(r['raw'], ensure_ascii=False)] for r in records if r['status'] == disposition])
    totals = []
    accepted = [r for r in records if r['status'] == 'accepted']
    with localcontext() as context:
        context.prec = 60
        for field in profile.get('totals', []):
            values = [Decimal(r['values'][field]) for r in accepted if r['values'][field] != '']
            totals.append([field, format(sum(values, Decimal(0)), 'f'), len(values), len(accepted) - len(values)])
    artifacts['summary.csv'] = safe_csv(['field', 'total', 'populated_accepted_rows', 'missing_accepted_rows'], totals, {1, 2, 3})
    artifacts['file_issues.csv'] = safe_csv(['source_file', 'reason'], issues)
    artifacts['import_history.csv'] = safe_csv(list(history[0]), [list(h.values()) for h in history], {3, 4, 5, 6, 7})
    artifacts['profile.json'] = canonical_json(profile)
    counts = {'input_rows': len(records), 'accepted_rows': len(accepted),
              'review_rows': sum(r['status'] == 'review' for r in records), 'skipped_rows': sum(r['status'] == 'skipped' for r in records),
              'file_issues': len(issues), 'files': len(files)}
    assert counts['input_rows'] == counts['accepted_rows'] + counts['review_rows'] + counts['skipped_rows']
    return {'counts': counts, 'totals': [{'field': r[0], 'total': r[1], 'populated': r[2], 'missing': r[3]} for r in totals],
            'history': history, 'preview': [{**r['values'], '__source_file': r['file'], '__source_record': r['record']} for r in accepted[:8]],
            'review_preview': [{'file': r['file'], 'record': r['record'], 'values': r['values'], 'reasons': r['errors']} for r in records if r['status'] == 'review'][:20],
            'complete': not issues}, artifacts
