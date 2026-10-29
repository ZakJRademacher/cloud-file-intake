"""S3 -> standard SQS -> Lambda adapter. AWS resources are not needed for local tests."""
import json
import os
from urllib.parse import unquote_plus
from .jobs import run_job
from .processor import MAX_BYTES
from .storage import S3Store



def handle_message(body, client, raw_bucket, results_bucket):
    event = json.loads(body)
    if event.get('Event') == 's3:TestEvent' and event.get('Service') == 'Amazon S3':
        return []
    records = event.get('Records')
    if not isinstance(records, list) or not records:
        raise ValueError('Expected an S3 notification')
    results = []
    store = S3Store(client, results_bucket)
    for record in records:
        if record.get('eventSource') != 'aws:s3' or not record.get('eventName', '').startswith('ObjectCreated:'):
            raise ValueError('Unsupported source notification')
        bucket = record['s3']['bucket']['name']
        obj = record['s3']['object']
        key = unquote_plus(obj['key'])
        version = obj.get('versionId')
        if bucket != raw_bucket or not key.startswith('incoming/') or not key.lower().endswith('.csv') or not version or version == 'null':
            raise ValueError('Source bucket, prefix, extension or object version does not match the contract')
        # Read the notified version, not whichever version happens to be current now.
        response = client.get_object(Bucket=bucket, Key=key, VersionId=version)
        stream = response['Body']
        try:
            data = stream.read(MAX_BYTES + 1)
        finally:
            stream.close()
        if len(data) > MAX_BYTES:
            # Do not claim to hash or process an original larger than the bounded read.
            # It will move to the dead-letter queue for operator review.
            raise ValueError('Source exceeds the 1,000,000-byte demo limit')
        result = run_job(store, data, {'mode': 'aws', 'bucket': bucket, 'key': key, 'version_id': version})
        print(json.dumps({'event': 'job_finished', 'job_id': result['job_id'],
                             'status': result['status'], 'reused': result['reused']}))
        results.append(result)
    return results


def handler(event, context, client=None):
    if client is None:
        import boto3
        from botocore.config import Config
        client = boto3.client('s3', config=Config(connect_timeout=3, read_timeout=5, retries={'max_attempts': 2}))
    failures = []
    for message in event['Records']:
        try:
            handle_message(message['body'], client, os.environ['RAW_BUCKET'], os.environ['RESULTS_BUCKET'])
        except Exception as error:
            # Do not log rows, filenames, full notifications or exception messages containing source data.
            print(json.dumps({'event': 'message_failed', 'message_id': message['messageId'], 'error_type': type(error).__name__}))
            failures.append({'itemIdentifier': message['messageId']})
    return {'batchItemFailures': failures}
