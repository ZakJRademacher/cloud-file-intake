"""Content-addressed, replay-safe jobs. A manifest is the publication boundary."""
import hashlib
import json
from .processor import CONTRACT_VERSION, InputError, transform


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode('utf-8')


def job_id(data):
    return digest(CONTRACT_VERSION.encode() + b'\0' + data)


def validate_manifest(store, key, expected_id):
    raw = store.get(key)
    if raw is None:
        return None
    manifest = json.loads(raw)
    if manifest.get('job_id') != expected_id or manifest.get('contract_version') != CONTRACT_VERSION:
        raise RuntimeError('Published manifest identity mismatch')
    files = manifest.get('files', {})
    expected = {'quarantine.json'} if manifest.get('status') == 'quarantined' else {
        'accepted.csv', 'needs_review.csv', 'skipped.csv', 'summary.csv'}
    if set(files) != expected:
        raise RuntimeError('Published manifest has an invalid file contract')
    for name, info in files.items():
        content = store.get(key.rsplit('/', 1)[0] + '/' + name)
        if content is None or digest(content) != info.get('sha256') or len(content) != info.get('bytes'):
            raise RuntimeError('Published output failed integrity verification')
    return manifest


def run_job(store, data, receipt):
    identifier = job_id(data)
    prefix = f'jobs/{identifier}'
    manifest_key = prefix + '/manifest.json'
    manifest = validate_manifest(store, manifest_key, identifier)
    reused = manifest is not None
    if manifest is None:
        try:
            counts, files = transform(data)
            status = 'completed_with_review' if counts['review_rows'] else 'completed'
        except InputError as error:
            counts, status = {}, 'quarantined'
            files = {'quarantine.json': json_bytes({'reason': str(error), 'action': 'Correct the source file and upload a new version.'})}
        manifest = {'job_id': identifier, 'contract_version': CONTRACT_VERSION,
                    'source_sha256': digest(data), 'source_bytes': len(data),
                    'status': status, 'counts': counts, 'files': {}}
        for name, content in sorted(files.items()):
            store.put(prefix + '/' + name, content, 'text/csv; charset=utf-8' if name.endswith('.csv') else 'application/json')
            manifest['files'][name] = {'sha256': digest(content), 'bytes': len(content)}
        # Readers must require this marker. An interrupted partial write has no completed manifest.
        store.put(manifest_key, json_bytes(manifest), 'application/json')
    identity = json_bytes(receipt)
    receipt_key = 'receipts/' + digest(identity) + '.json'
    store.put(receipt_key, json_bytes({'job_id': identifier, 'source': receipt}), 'application/json')
    return {**manifest, 'reused': reused, 'manifest_key': manifest_key, 'receipt_key': receipt_key}
