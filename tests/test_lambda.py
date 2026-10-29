import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import quote_plus
from src.lambda_handler import handler, handle_message

DATA=(Path(__file__).resolve().parents[1]/'data/samples/weekly-sales.csv').read_bytes()


class NotFound(Exception):
    response={'Error':{'Code':'NoSuchKey'}}


class FakeS3:
    def __init__(self):self.objects={};self.reads=[];self.fail=False
    def get_object(self,**kw):
        self.reads.append(kw)
        key=(kw['Bucket'],kw['Key'],kw.get('VersionId'))
        if key not in self.objects:raise NotFound()
        return {'Body':io.BytesIO(self.objects[key])}
    def put_object(self,**kw):
        if self.fail:raise PermissionError('Injected storage failure')
        self.objects[(kw['Bucket'],kw['Key'],None)]=kw['Body']


def notification(key='incoming/sales + copy.csv',version='version-1'):
    return json.dumps({'Records':[{'eventSource':'aws:s3','eventName':'ObjectCreated:Put',
        's3':{'bucket':{'name':'raw'},'object':{'key':quote_plus(key),'versionId':version}}}]})


class LambdaTests(unittest.TestCase):
    def setUp(self):
        self.s3=FakeS3();self.s3.objects[('raw','incoming/sales + copy.csv','version-1')]=DATA

    def test_exact_version_and_encoded_key_are_used_and_replays_reuse_results(self):
        self.s3.objects[('raw','incoming/sales + copy.csv',None)]=b'a newer bad version'
        a=handle_message(notification(),self.s3,'raw','results')[0]
        b=handle_message(notification(),self.s3,'raw','results')[0]
        self.assertEqual(a['counts']['net_cents'],2050);self.assertTrue(b['reused'])
        self.assertIn({'Bucket':'raw','Key':'incoming/sales + copy.csv','VersionId':'version-1'},self.s3.reads)

    def test_partial_batch_returns_only_the_operational_failure(self):
        event={'Records':[{'messageId':'good','body':notification()}, {'messageId':'bad','body':'not JSON'}]}
        with patch.dict(os.environ,{'RAW_BUCKET':'raw','RESULTS_BUCKET':'results'}):
            self.assertEqual(handler(event,None,self.s3),{'batchItemFailures':[{'itemIdentifier':'bad'}]})

    def test_malformed_input_is_quarantined_and_acknowledged(self):
        self.s3.objects[('raw','incoming/sales + copy.csv','version-1')]=b'bad,header\n'
        with patch.dict(os.environ,{'RAW_BUCKET':'raw','RESULTS_BUCKET':'results'}):
            result=handler({'Records':[{'messageId':'bad-schema','body':notification()}]},None,self.s3)
        self.assertEqual(result,{'batchItemFailures':[]})
        self.assertTrue(any(key[1].endswith('quarantine.json') for key in self.s3.objects))

    def test_storage_access_failure_is_retried(self):
        self.s3.fail=True
        with patch.dict(os.environ,{'RAW_BUCKET':'raw','RESULTS_BUCKET':'results'}):
            result=handler({'Records':[{'messageId':'retry','body':notification()}]},None,self.s3)
        self.assertEqual(result,{'batchItemFailures':[{'itemIdentifier':'retry'}]})

    def test_missing_version_wrong_prefix_and_oversized_objects_fail(self):
        for body in [notification(version=None),notification(key='elsewhere/x.csv')]:
            with self.assertRaises(ValueError):handle_message(body,self.s3,'raw','results')
        self.s3.objects[('raw','incoming/sales + copy.csv','version-1')]=b'x'*1_000_001
        with self.assertRaisesRegex(ValueError,'exceeds'):handle_message(notification(),self.s3,'raw','results')

    def test_s3_configuration_test_is_acknowledged(self):
        self.assertEqual(handle_message(json.dumps({'Service':'Amazon S3','Event':'s3:TestEvent'}),self.s3,'raw','results'),[])


if __name__=='__main__':unittest.main()
