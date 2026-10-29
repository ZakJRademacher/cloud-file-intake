"""Fetch the official Windows CLI into a local tools cache, verifying its SHA-256.

No system PATH or cloud account configuration is changed.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import urllib.request
import zipfile

VERSION='1.17.0'
NAME=f'terraform_{VERSION}_windows_amd64.zip'
BASE=f'https://releases.hashicorp.com/terraform/{VERSION}/'


def main():
    root=Path(__file__).resolve().parents[1]
    target=Path(os.environ['LOCALAPPDATA'])/'cloud-file-intake-tools'/f'terraform-{VERSION}'
    target.mkdir(parents=True,exist_ok=True)
    checks=urllib.request.urlopen(BASE+f'terraform_{VERSION}_SHA256SUMS',timeout=30).read().decode()
    expected=next(line.split()[0] for line in checks.splitlines() if line.split()[-1]==NAME)
    data=urllib.request.urlopen(BASE+NAME,timeout=60).read()
    actual=hashlib.sha256(data).hexdigest()
    assert expected==actual,'Official download did not match the published checksum'
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in ['terraform.exe','LICENSE.txt']:
            if name in archive.namelist():(target/name).write_bytes(archive.read(name))
    record={'version':VERSION,'url':BASE+NAME,'zip_sha256':actual,'executable':str(target/'terraform.exe'),
            'verification':'SHA-256 compared with the official HTTPS checksum manifest; detached signature not verified.'}
    evidence=root/'evidence';evidence.mkdir(exist_ok=True)
    (evidence/'terraform-tool.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
