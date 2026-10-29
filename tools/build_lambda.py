"""Build a deterministic deployment ZIP with pinned SDK dependencies outside OneDrive."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lock',action='store_true',help='Resolve a fresh dependency lock from requirements.txt.')
    args=parser.parse_args()
    build=ROOT/'build';build.mkdir(exist_ok=True)
    lock=ROOT/'requirements.lock.txt'
    requirements=ROOT/'requirements.txt' if args.lock or not lock.exists() else lock
    with tempfile.TemporaryDirectory(prefix='cloud-file-intake-package-') as temporary:
        stage=Path(temporary)
        subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--only-binary=:all:',
                        '--no-compile','--target',str(stage),'-r',str(requirements)],check=True)
        dependencies=sorted(f'{d.metadata["Name"]}=={d.version}' for d in importlib.metadata.distributions(path=[str(stage)]))
        resolved='\n'.join(dependencies)+'\n'
        if requirements.name=='requirements.txt':lock.write_text(resolved,encoding='utf-8')
        else:assert set(resolved.splitlines())==set(lock.read_text(encoding='utf-8').splitlines()),'Dependencies differ from the lock'
        entries={}
        for path in stage.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':
                entries[path.relative_to(stage).as_posix()]=path.read_bytes()
        for path in (ROOT/'src').glob('*.py'):
            if path.name in ['cli.py','local_web.py']:continue
            entries['src/'+path.name]=path.read_bytes()
        archive=build/'lambda.zip'
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for name,data in sorted(entries.items()):
                info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=0o644<<16;z.writestr(info,data)
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None and 'src/lambda_handler.py' in z.namelist()
        record={'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size,
                'dependencies':dependencies,'entries':len(entries),'deployed':False}
        evidence=ROOT/'evidence';evidence.mkdir(exist_ok=True)
        (evidence/'lambda-package.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        print(json.dumps(record,indent=2))


if __name__=='__main__':main()
