from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from src.local_web import make_handler
from src.storage import LocalStore


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(LocalStore(cls.temp.name),'test-token'))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.temp.cleanup()

    def request(self,path,post=False,headers=None,data=b''):
        request=urllib.request.Request(self.base+path,data=data if post else None,headers=headers or {},method='POST' if post else 'GET')
        try:
            with urllib.request.urlopen(request,timeout=3) as r:return r.status,r.read(),dict(r.headers)
        except urllib.error.HTTPError as r:return r.code,r.read(),dict(r.headers)

    def test_local_upload_replay_and_export_download(self):
        headers={'X-Local-Token':'test-token','Origin':self.base}
        status,body,_=self.request('/api/demo/weekly-sales.csv',True,headers)
        self.assertEqual(status,200);first=json.loads(body);self.assertEqual(first['counts']['net_cents'],2050)
        self.assertEqual(first['source_label'],'weekly-sales.csv')
        _,body,_=self.request('/api/demo/weekly-sales.csv',True,headers);self.assertTrue(json.loads(body)['reused'])
        status,data,h=self.request(f'/api/jobs/{first["job_id"]}/files/summary.csv')
        self.assertEqual(status,200);self.assertIn(b'Office,550,3',data);self.assertIn('attachment',h['Content-Disposition'])
        self.assertEqual(self.request('/api/jobs/'+first['job_id']+'/files/source.csv')[0],404)

    def test_missing_token_cross_origin_and_wrong_host_are_rejected(self):
        self.assertEqual(self.request('/api/demo/weekly-sales.csv',True)[0],403)
        self.assertEqual(self.request('/api/demo/weekly-sales.csv',True,{'X-Local-Token':'test-token','Origin':'https://example.com'})[0],403)
        self.assertEqual(self.request('/api/jobs',headers={'Host':'untrusted.example'})[0],403)

    def test_page_is_explicit_about_local_mode_and_jobs_are_json(self):
        status,page,h=self.request('/')
        self.assertEqual(status,200);self.assertIn(b'Local lab',page);self.assertIn(b'test-token',page)
        self.assertIn("frame-ancestors 'none'",h['Content-Security-Policy'])
        _,body,_=self.request('/api/jobs');self.assertFalse(json.loads(body)['aws_connected'])


if __name__=='__main__':unittest.main()
