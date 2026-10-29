"""Local profile storage, repeatable batch publication, and workbench examples."""
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import threading
from .profile_engine import (ENGINE_VERSION, MAX_TOTAL_BYTES, MAX_FILE_BYTES, MAX_FILES,
                             ProfileError, canonical_json, consolidate, inspect_file, validate_profile)


def sample_bundle(kind):
    if kind == 'sales':
        profile = {'version': 1, 'name': 'Sales line exports', 'columns': [
            {'id': 'line_id', 'type': 'text', 'required': True}, {'id': 'sale_date', 'type': 'date', 'required': True},
            {'id': 'category', 'type': 'text', 'required': True}, {'id': 'amount', 'type': 'decimal', 'scale': 4, 'required': True}],
            'keys': ['line_id'], 'duplicates': 'keys', 'extra_columns': 'preserve', 'totals': ['amount'], 'formats': [
                {'name': 'Standard CSV', 'delimiter': ',', 'encoding': 'utf-8-sig', 'date_format': 'YYYY-MM-DD',
                 'decimal_mark': '.', 'group_mark': '', 'mapping': {'line_id': 'Line ID', 'sale_date': 'Date', 'category': 'Category', 'amount': 'Sales'}},
                {'name': 'European export', 'delimiter': ';', 'encoding': 'utf-8-sig', 'date_format': 'DD/MM/YYYY',
                 'decimal_mark': ',', 'group_mark': '.', 'mapping': {'line_id': 'Reference', 'sale_date': 'Posted', 'category': 'Department', 'amount': 'Net'}}]}
        files = [
            {'name': '01_sales.csv', 'format': 'Standard CSV', 'data': 'Line ID,Date,Category,Sales\n0001,2026-10-01,Office,10.1250\n0002,2026-10-02,Food,20.50\n0003,2026-10-03,Office,5\n0004,2026-10-04,Service,-2.25\n0005,2026-02-30,Office,4\n'},
            {'name': '02_export.csv', 'format': 'European export', 'data': 'Reference;Posted;Department;Net\n0001;01/10/2026;Office;10,1250\n0002;02/10/2026;Food;21,50\n0006;06/10/2026;Food;1.234,5678\n0007;07/10/2026;Service;0\n'}]
    elif kind == 'tickets':
        profile = {'version': 1, 'name': 'Service ticket exports', 'columns': [
            {'id': 'ticket_id', 'type': 'text', 'required': True}, {'id': 'opened', 'type': 'date', 'required': True},
            {'id': 'team', 'type': 'text', 'required': True}, {'id': 'status', 'type': 'text', 'required': True, 'allowed': ['Open', 'Closed']},
            {'id': 'hours', 'type': 'decimal', 'scale': 2, 'required': False, 'min': '0'}],
            'keys': ['ticket_id'], 'duplicates': 'keys', 'extra_columns': 'preserve', 'totals': ['hours'], 'formats': [
                {'name': 'Helpdesk CSV', 'delimiter': ',', 'encoding': 'utf-8-sig', 'date_format': 'YYYY-MM-DD',
                 'decimal_mark': '.', 'group_mark': '', 'mapping': {'ticket_id': 'Ticket', 'opened': 'Opened', 'team': 'Team', 'status': 'Status', 'hours': 'Hours'}}]}
        files = [
            {'name': '01_tickets.csv', 'format': 'Helpdesk CSV', 'data': 'Ticket,Opened,Team,Status,Hours\nT001,2026-10-01,Support,Closed,1.25\nT002,2026-10-02,IT,Open,\nT003,2026-10-03,Support,Pending,0.5\n'},
            {'name': '02_tickets.csv', 'format': 'Helpdesk CSV', 'data': 'Ticket,Opened,Team,Status,Hours\nT001,2026-10-01,Support,Closed,1.25\nT004,2026-10-04,IT,Closed,2.75\nT005,2026-10-05,IT,Closed,-1\n'}]
    else: raise ProfileError('Unknown example.')
    return {'profile': profile, 'files': [{**f, 'data': base64.b64encode(f['data'].encode()).decode()} for f in files]}


class Workbench:
    def __init__(self, root):
        self.root = Path(root) / 'workbench'
        self.lock = threading.RLock()

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.' + secrets.token_hex(8) + '.tmp')
        temporary.write_bytes(data); temporary.replace(path)

    def profiles(self):
        with self.lock:
            output = []
            for path in sorted((self.root / 'profiles').glob('*.json')):
                try: output.append({'id': path.stem, 'profile': json.loads(path.read_bytes())})
                except (OSError, ValueError): continue
            return output

    def save_profile(self, profile, identifier=None):
        profile = validate_profile(profile)
        if identifier is not None and (not isinstance(identifier, str) or len(identifier) != 32 or any(x not in '0123456789abcdef' for x in identifier)):
            raise ProfileError('Invalid saved profile ID.')
        identifier = identifier or secrets.token_hex(16)
        with self.lock:
            self.write(self.root / 'profiles' / (identifier + '.json'), canonical_json(profile))
        return {'id': identifier, 'profile': profile}

    @staticmethod
    def unpack_files(files):
        if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES: raise ProfileError('Choose 1–20 files.')
        unpacked = []; size = 0
        for item in files:
            if not isinstance(item, dict) or not isinstance(item.get('data'), str): raise ProfileError('File contents must be base64 text.')
            if len(item['data']) > (MAX_FILE_BYTES * 4 // 3 + 8): raise ProfileError('Each file must be at most 5 MB.')
            try: data = base64.b64decode(item['data'], validate=True)
            except (ValueError, TypeError) as error: raise ProfileError('Invalid base64 file contents.') from error
            size += len(data)
            if size > MAX_TOTAL_BYTES or len(data) > MAX_FILE_BYTES: raise ProfileError('Use files up to 5 MB each and 20 MB combined.')
            unpacked.append({'name': item.get('name'), 'format': item.get('format'), 'data': data})
        return unpacked

    def inspect(self, value):
        files = self.unpack_files([value])
        return inspect_file(files[0]['data'], value.get('delimiter', ','), value.get('encoding', 'utf-8-sig'))

    def run(self, profile, encoded_files):
        profile = validate_profile(profile); files = self.unpack_files(encoded_files)
        identity = {'engine': ENGINE_VERSION, 'profile': profile,
                    'sources': sorted([{'name': f['name'], 'format': f['format'], 'sha256': hashlib.sha256(f['data']).hexdigest()} for f in files], key=lambda f: str(f['name']))}
        identifier = hashlib.sha256(canonical_json(identity)).hexdigest()
        target = self.root / 'jobs' / identifier
        with self.lock:
            manifest_path = target / 'manifest.json'
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_bytes())
                for name, record in manifest['artifacts'].items():
                    data = (target / name).read_bytes()
                    if hashlib.sha256(data).hexdigest() != record['sha256'] or len(data) != record['bytes']:
                        raise RuntimeError('A saved output failed integrity verification. Inspect local results before retrying.')
                return {**manifest, 'reused': True}
            result, artifacts = consolidate(profile, files)
            # Preserve the exact uploaded bytes independently of displayed/normalized output.
            for index, source in enumerate(sorted(files, key=lambda f: f['name'])):
                self.write(target / 'raw' / f'{index:02d}.csv', source['data'])
            descriptors = {}
            for name, data in artifacts.items():
                self.write(target / name, data)
                descriptors[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
            manifest = {**result, 'job_id': identifier, 'engine': ENGINE_VERSION, 'profile_name': profile['name'],
                        'profile_sha256': hashlib.sha256(canonical_json(profile)).hexdigest(), 'sources': identity['sources'],
                        'created_at': datetime.now(timezone.utc).isoformat(), 'artifacts': descriptors,
                        'status': 'completed' if result['complete'] else 'incomplete_file_errors'}
            self.write(manifest_path, canonical_json(manifest))
            return {**manifest, 'reused': False}

    def jobs(self):
        with self.lock:
            paths = sorted((self.root / 'jobs').glob('*/manifest.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:40]
            results = []
            for p in paths:
                try:
                    value = json.loads(p.read_bytes())
                    results.append({k: value[k] for k in ['job_id', 'profile_name', 'status', 'created_at', 'counts']})
                except (ValueError, OSError, KeyError): continue
            return results

    def download(self, identifier, name):
        if len(identifier) != 64 or any(x not in '0123456789abcdef' for x in identifier): return None
        target = self.root / 'jobs' / identifier
        with self.lock:
            path = target / 'manifest.json'
            if not path.exists(): return None
            manifest = json.loads(path.read_bytes())
            if name == 'manifest.json': return path.read_bytes()
            if name not in manifest['artifacts']: return None
            data = (target / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != manifest['artifacts'][name]['sha256']:
                raise RuntimeError('Saved download failed integrity verification.')
            return data
