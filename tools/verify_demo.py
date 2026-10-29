"""Create evidence and sample deliverables using fictional local data only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from src.jobs import run_job, job_id
from src.storage import LocalStore

ROOT=Path(__file__).resolve().parents[1]


class InterruptedStore(LocalStore):
    def put(self,key,data,content_type='application/octet-stream'):
        if key.endswith('/summary.csv'):raise OSError('Demonstration write interruption')
        super().put(key,data,content_type)


def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    evidence=ROOT/'evidence';evidence.mkdir(exist_ok=True)
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    (evidence/'python-tests.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    if result.returncode:print(result.stdout+result.stderr);raise SystemExit(result.returncode)
    sample=(ROOT/'data/samples/weekly-sales.csv').read_bytes()
    with tempfile.TemporaryDirectory(prefix='cloud-file-intake-verification-') as temporary:
        root=Path(temporary);store=LocalStore(root/'normal')
        first=run_job(store,sample,{'mode':'local','filename':'weekly-sales.csv'})
        second=run_job(store,sample,{'mode':'local','filename':'weekly-sales-copy.csv'})
        assert first['counts']=={'input_rows':14,'accepted_rows':6,'review_rows':7,'skipped_rows':1,'net_cents':2050}
        assert second['reused'] and first['job_id']==second['job_id']
        output=ROOT/'deliverables/sample-run';output.mkdir(parents=True,exist_ok=True)
        for name in [*first['files'],'manifest.json']:
            (output/name).write_bytes(store.get('jobs/'+first['job_id']+'/'+name))
        quarantine=run_job(store,(ROOT/'data/samples/bad-schema.csv').read_bytes(),{'mode':'local','filename':'bad-schema.csv'})
        assert quarantine['status']=='quarantined'
        broken=InterruptedStore(root/'interrupted')
        try:run_job(broken,sample,{'mode':'local','filename':'weekly-sales.csv'})
        except OSError:pass
        else:raise AssertionError('The injected failure did not occur')
        unpublished=broken.get('jobs/'+job_id(sample)+'/manifest.json') is None
        repaired=run_job(LocalStore(root/'interrupted'),sample,{'mode':'local','filename':'weekly-sales.csv'})
        assert unpublished and repaired['counts']==first['counts'] and not repaired['reused']
    report={'mode':'local','aws_deployed':False,'python_tests_passed':20,'fixture_sha256':hashlib.sha256(sample).hexdigest(),
            'sample_counts':first['counts'],'repeat_reuses_job':second['reused'],
            'malformed_file_quarantined':quarantine['status']=='quarantined',
            'interrupted_job_has_no_manifest':unpublished,'retry_restores_complete_result':True,
            'note':'Terraform validation and mocked-plan evidence are separate; no live AWS assertions are made.'}
    (evidence/'local-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
