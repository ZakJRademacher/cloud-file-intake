from http.server import ThreadingHTTPServer
import base64
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
from src.local_web import main, make_handler
from src.storage import LocalStore
from src.workbench import sample_bundle


class WorkbenchWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(LocalStore(cls.temp.name),'profile-token'))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.temp.cleanup()

    def request(self,path,body=None,headers=None):
        request=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,
            headers=headers if headers is not None else {'X-Local-Token':'profile-token','Origin':self.base,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=5) as response:return response.status,response.read()
        except urllib.error.HTTPError as error:return error.code,error.read()

    def test_end_to_end_save_inspect_publish_and_download(self):
        sample=sample_bundle('tickets')
        status,page=self.request('/workspace');self.assertEqual(status,200);self.assertIn(b'profile-token',page)
        status,saved=self.request('/api/workbench/profiles',{'profile':sample['profile']});self.assertEqual(status,200)
        status,profiles=self.request('/api/workbench/profiles');self.assertIn(json.loads(saved)['id'],profiles.decode())
        status,preview=self.request('/api/workbench/inspect',sample['files'][0]);self.assertEqual(json.loads(preview)['rows'],3)
        status,body=self.request('/api/workbench/run',sample);self.assertEqual(status,200);result=json.loads(body)
        self.assertEqual(result['counts']['accepted_rows'],3)
        _,again=self.request('/api/workbench/run',sample);self.assertTrue(json.loads(again)['reused'])
        status,output=self.request(f'/api/workbench/jobs/{result["job_id"]}/files/summary.csv')
        self.assertEqual(status,200);self.assertIn(b'hours,4.00,2,1',output)
        self.assertEqual(self.request(f'/api/workbench/jobs/{result["job_id"]}/files/raw.csv')[0],404)

    def test_mutations_require_local_token_and_origin(self):
        sample=sample_bundle('tickets')
        self.assertEqual(self.request('/api/workbench/run',sample,headers={})[0],403)
        self.assertEqual(self.request('/api/workbench/profiles',{'profile':sample['profile']},headers={'X-Local-Token':'profile-token','Origin':'https://outside.example'})[0],403)
        self.assertEqual(self.request('/api/workbench/jobs',headers={'Host':'outside.example'})[0],403)

    def test_bad_profile_bad_encoding_and_file_bytes_explain_failure(self):
        self.assertEqual(self.request('/api/workbench/validate',{'profile':{}})[0],400)
        self.assertEqual(self.request('/api/workbench/inspect',{'name':'x.csv','data':'%%%%'})[0],400)
        status,body=self.request('/api/workbench/inspect',{'name':'x.csv','data':base64.b64encode(b'ID\n1\n').decode(),'encoding':'wrong'})
        self.assertEqual(status,400);self.assertIn(b'encoding',body)

    def test_launcher_reuses_verified_running_workbench(self):
        with patch('sys.argv',['local_web','--port',str(self.server.server_port),'--workspace','--open-browser','--store',self.temp.name]),patch('webbrowser.open') as opened:
            main()
        opened.assert_called_once_with(self.base+'/workspace')


if __name__=='__main__':unittest.main()
