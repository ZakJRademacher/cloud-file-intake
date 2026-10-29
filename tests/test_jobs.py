import json
from pathlib import Path
import tempfile
import unittest
from src.jobs import run_job, job_id
from src.storage import LocalStore

SAMPLE=(Path(__file__).resolve().parents[1]/'data/samples/weekly-sales.csv').read_bytes()


class FailingStore(LocalStore):
    def put(self,key,data,content_type='application/octet-stream'):
        if key.endswith('/summary.csv'): raise OSError('Injected output write failure')
        super().put(key,data,content_type)


class JobTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store=LocalStore(self.temp.name)

    def test_repeat_delivery_has_one_result_with_separate_source_receipts(self):
        first=run_job(self.store,SAMPLE,{'filename':'a.csv'})
        before={p.name:p.read_bytes() for p in self.store.path('jobs/'+first['job_id']).iterdir()}
        second=run_job(self.store,SAMPLE,{'filename':'b.csv'})
        self.assertFalse(first['reused']);self.assertTrue(second['reused'])
        self.assertEqual(first['job_id'],second['job_id'])
        self.assertEqual(len(list(self.store.path('jobs').iterdir())),1)
        self.assertEqual(len(list(self.store.path('receipts').iterdir())),2)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.store.path('jobs/'+first['job_id']).iterdir()})

    def test_failed_publish_has_no_manifest_and_retry_repairs_partial_outputs(self):
        broken=FailingStore(self.temp.name)
        with self.assertRaises(OSError):run_job(broken,SAMPLE,{'filename':'a.csv'})
        self.assertIsNone(self.store.get('jobs/'+job_id(SAMPLE)+'/manifest.json'))
        result=run_job(self.store,SAMPLE,{'filename':'a.csv'})
        self.assertFalse(result['reused']);self.assertEqual(result['counts']['net_cents'],2050)
        self.assertTrue(run_job(self.store,SAMPLE,{'filename':'a.csv'})['reused'])

    def test_corrupt_complete_result_is_detected_instead_of_silently_reused(self):
        result=run_job(self.store,SAMPLE,{'filename':'a.csv'})
        self.store.put('jobs/'+result['job_id']+'/summary.csv',b'corrupt')
        with self.assertRaisesRegex(RuntimeError,'integrity'):run_job(self.store,SAMPLE,{'filename':'a.csv'})

    def test_schema_error_is_terminal_quarantine_with_explanation(self):
        result=run_job(self.store,b'wrong,header\n1,2\n',{'filename':'bad.csv'})
        self.assertEqual(result['status'],'quarantined')
        self.assertEqual(set(result['files']),{'quarantine.json'})
        reason=json.loads(self.store.get('jobs/'+result['job_id']+'/quarantine.json'))['reason']
        self.assertIn('invalid_header',reason)
        self.assertTrue(run_job(self.store,b'wrong,header\n1,2\n',{'filename':'bad.csv'})['reused'])

    def test_local_store_rejects_traversal_and_absolute_keys(self):
        for key in ['../escape','/absolute','x/../escape','C:/file','a\\b','a//b']:
            with self.subTest(key=key), self.assertRaises(ValueError):self.store.put(key,b'bad')


if __name__=='__main__':unittest.main()
