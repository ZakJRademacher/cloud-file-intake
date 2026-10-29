"""Small object-store adapters; local writes replace files atomically."""
import os
from pathlib import Path, PurePosixPath
import tempfile


def safe_key(key):
    if not isinstance(key, str) or not key or '\\' in key or ':' in key:
        raise ValueError('Invalid object key')
    path = PurePosixPath(key)
    if path.is_absolute() or any(x in ('', '.', '..') for x in key.split('/')):
        raise ValueError('Invalid object key')
    return path


class LocalStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key):
        path = (self.root / Path(*safe_key(key).parts)).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('Object key leaves the store')
        return path

    def get(self, key):
        path = self.path(key)
        try:
            return path.read_bytes()
        except FileNotFoundError:
            return None

    def put(self, key, data, content_type='application/octet-stream'):
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        name = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
                name = f.name
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)


class S3Store:
    def __init__(self, client, bucket):
        self.client, self.bucket = client, bucket

    def get(self, key):
        safe_key(key)
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)['Body'].read()
        except Exception as error:
            # Access denied and service errors must be retried, never treated as missing.
            code = getattr(error, 'response', {}).get('Error', {}).get('Code')
            if code in ('NoSuchKey', '404'):
                return None
            raise

    def put(self, key, data, content_type='application/octet-stream'):
        safe_key(key)
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
