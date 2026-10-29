"""Extract the built ZIP into a disposable directory and exercise its bundled SDK.

The S3 client uses explicit fictional credentials and botocore Stubber. No AWS
request or credential lookup occurs. This checks packaging and SDK call shapes.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
CODE=r'''
import io,json,sys
sys.path.insert(0,sys.argv[1])
import boto3
from botocore.response import StreamingBody
from botocore.stub import Stubber,ANY
from src.lambda_handler import handle_message
client=boto3.client('s3',region_name='us-west-2',aws_access_key_id='fictional-testing',aws_secret_access_key='fictional-testing')
data=b'record_id,sale_date,category,quantity,unit_price_cents\n001,2026-10-01,Office,2,250\n'
stub=Stubber(client)
stub.add_response('get_object',{'Body':StreamingBody(io.BytesIO(data),len(data))},{'Bucket':'raw','Key':'incoming/test.csv','VersionId':'v1'})
stub.add_client_error('get_object',service_error_code='NoSuchKey',http_status_code=404,expected_params={'Bucket':'results','Key':ANY})
for name in ['accepted.csv','needs_review.csv','skipped.csv','summary.csv']:
    stub.add_response('put_object',{}, {'Bucket':'results','Key':ANY,'Body':ANY,'ContentType':'text/csv; charset=utf-8'})
for _ in range(2):
    stub.add_response('put_object',{}, {'Bucket':'results','Key':ANY,'Body':ANY,'ContentType':'application/json'})
body=json.dumps({'Records':[{'eventSource':'aws:s3','eventName':'ObjectCreated:Put','s3':{'bucket':{'name':'raw'},'object':{'key':'incoming/test.csv','versionId':'v1'}}}]})
with stub:
    result=handle_message(body,client,'raw','results')[0]
    stub.assert_no_pending_responses()
assert result['counts']['net_cents']==500,result
assert result['counts']['accepted_rows']==1,result
print(json.dumps({'sdk':boto3.__version__,'package_imported':True,'stubbed_s3_adapter_passed':True,'aws_requests_sent':False}))
'''


def main():
    with tempfile.TemporaryDirectory(prefix='cloud-file-intake-smoke-') as temporary:
        with zipfile.ZipFile(ROOT/'build/lambda.zip') as archive:archive.extractall(temporary)
        result=subprocess.run([sys.executable,'-c',CODE,temporary],cwd=temporary,capture_output=True,text=True,encoding='utf-8')
        (ROOT/'evidence/package-smoke.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        print(result.stdout+result.stderr)
        if result.returncode:raise SystemExit(result.returncode)


if __name__=='__main__':main()
