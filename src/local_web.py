"""A loopback-only learning console for the actual processor; no AWS calls."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
from urllib.parse import unquote, urlparse
from .jobs import digest, run_job
from .processor import MAX_BYTES
from .storage import LocalStore
from .workbench import Workbench, sample_bundle
from .profile_engine import ProfileError, validate_profile

ROOT=Path(__file__).resolve().parents[1]
SAMPLES={'weekly-sales.csv','alternate-headers.csv','bad-schema.csv'}


def make_handler(store, token):
    workbench=Workbench(store.root)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass

        def send(self,status,body,kind='application/json',filename=None):
            self.send_response(status)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
            self.end_headers();self.wfile.write(body)

        def json(self,status,data):self.send(status,json.dumps(data).encode())

        def host_ok(self):
            return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'

        def do_GET(self):
            if not self.host_ok():return self.json(403,{'error':'Open the printed 127.0.0.1 address.'})
            path=urlparse(self.path).path
            if path in ['/workspace','/workspace/','/workbench.js','/workbench.css','/studio.css']:
                name='workbench.html' if path.startswith('/workspace') else path[1:]
                data=(ROOT/'web'/name).read_bytes().replace(b'__LOCAL_TOKEN__',token.encode())
                kind={'workbench.html':'text/html; charset=utf-8','workbench.js':'text/javascript; charset=utf-8','workbench.css':'text/css; charset=utf-8','studio.css':'text/css; charset=utf-8'}[name]
                return self.send(200,data,kind)
            if path=='/api/workbench/profiles':return self.json(200,{'profiles':workbench.profiles()})
            if path=='/api/workbench/jobs':return self.json(200,{'jobs':workbench.jobs()})
            if path.startswith('/api/workbench/example/'):
                try:return self.json(200,sample_bundle(path.rsplit('/',1)[-1]))
                except ProfileError as error:return self.json(400,{'error':str(error)})
            match=re.fullmatch(r'/api/workbench/jobs/([a-f0-9]{64})/files/([a-z_.]+)',path)
            if match:
                try:
                    data=workbench.download(*match.groups())
                    if data is not None:return self.send(200,data,'application/octet-stream',match.group(2))
                except (RuntimeError,OSError,ValueError):return self.json(409,{'error':'Saved output failed verification or is unavailable.'})
                return self.json(404,{'error':'Published file not found.'})
            if path in ['/','/app.js','/styles.css']:
                name='index.html' if path=='/' else path[1:]
                data=(ROOT/'web'/name).read_bytes().replace(b'__LOCAL_TOKEN__',token.encode())
                kind={'index.html':'text/html; charset=utf-8','app.js':'text/javascript; charset=utf-8','styles.css':'text/css; charset=utf-8'}[name]
                return self.send(200,data,kind)
            if path=='/api/jobs':
                base=store.path('jobs'); manifests=[]
                if base.exists():
                    paths=sorted(base.glob('*/manifest.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:100]
                    for p in paths:
                        try:manifests.append(json.loads(p.read_text(encoding='utf-8')))
                        except (ValueError,OSError):continue
                return self.json(200,{'mode':'local','aws_connected':False,'jobs':manifests})
            match=re.fullmatch(r'/api/jobs/([a-f0-9]{64})/files/([a-z_.]+)',path)
            if match:
                identifier,name=match.groups()
                raw=store.get(f'jobs/{identifier}/manifest.json')
                if raw:
                    manifest=json.loads(raw)
                    if name=='manifest.json' or name in manifest['files']:
                        data=store.get(f'jobs/{identifier}/{name}')
                        if data is not None:return self.send(200,data,'application/octet-stream',name)
            return self.json(404,{'error':'File or route not found.'})

        def do_POST(self):
            origin=self.headers.get('Origin')
            expected=f'http://127.0.0.1:{self.server.server_port}'
            if not self.host_ok() or self.headers.get('X-Local-Token')!=token or (origin and origin!=expected):
                return self.json(403,{'error':'This local request was not authorized.'})
            try:
                length=int(self.headers.get('Content-Length','-1'))
                if urlparse(self.path).path.startswith('/api/workbench/'):
                    if not 0<=length<=28_000_000:return self.json(413,{'error':'Use a batch up to 20 MB; each file up to 5 MB.'})
                    body=self.rfile.read(length)
                    if len(body)!=length:return self.json(400,{'error':'Incomplete request.'})
                    try:
                        value=json.loads(body)
                        if not isinstance(value,dict):raise ProfileError('Use a JSON object.')
                        path=urlparse(self.path).path
                        if path=='/api/workbench/inspect':return self.json(200,workbench.inspect(value))
                        if path=='/api/workbench/validate':return self.json(200,{'profile':validate_profile(value.get('profile'))})
                        if path=='/api/workbench/profiles':return self.json(200,workbench.save_profile(value.get('profile'),value.get('id')))
                        if path=='/api/workbench/run':return self.json(200,workbench.run(value.get('profile'),value.get('files')))
                        return self.json(404,{'error':'Route not found.'})
                    except (ProfileError,ValueError,TypeError,KeyError) as error:return self.json(400,{'error':str(error)})
                if not 0<=length<=MAX_BYTES:return self.json(413,{'error':'Use a CSV up to 1,000,000 bytes.'})
                path=urlparse(self.path).path
                if path=='/api/upload':
                    data=self.rfile.read(length)
                    if len(data)!=length:return self.json(400,{'error':'Incomplete upload.'})
                    name=unquote(self.headers.get('X-Filename','upload.csv'))[:180]
                    name=name.replace('\\','/').rsplit('/',1)[-1]
                elif path.startswith('/api/demo/') and path.rsplit('/',1)[-1] in SAMPLES:
                    self.rfile.read(length)
                    name=path.rsplit('/',1)[-1];data=(ROOT/'data/samples'/name).read_bytes()
                else:return self.json(404,{'error':'Route not found.'})
                raw_key='raw/'+digest(data)+'.csv'
                store.put(raw_key,data,'text/csv')
                result=run_job(store,data,{'mode':'local','filename':name,'raw_key':raw_key})
                return self.json(200,{**result,'source_label':name})
            except Exception as error:
                return self.json(500,{'error':'Processing did not finish. No new completed manifest was published. Inspect the local logs.','error_type':type(error).__name__})
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8801)
    parser.add_argument('--store',type=Path,default=ROOT/'local-data')
    parser.add_argument('--open-browser',action='store_true')
    parser.add_argument('--workspace',action='store_true',help='Open the reusable CSV workbench instead of the original sales lab.')
    args=parser.parse_args()
    store=LocalStore(args.store)
    if args.open_browser and args.port:
        from urllib.request import urlopen
        existing=f'http://127.0.0.1:{args.port}/'+('workspace' if args.workspace else '')
        try:
            with urlopen(existing,timeout=2) as response:page=response.read(100_000)
            marker=b'Intake Workbench' if args.workspace else b'Cloud File Intake'
            if marker in page and b'local-token' in page:
                import webbrowser
                webbrowser.open(existing)
                print('The local application is already running: '+existing,flush=True)
                return
        except OSError:pass
    server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(store,secrets.token_urlsafe(32)))
    url=f'http://127.0.0.1:{server.server_port}/'+('workspace' if args.workspace else '')
    print(f'Cloud File Intake — LOCAL ONLY\n{url}\nStore: {store.root}\nCtrl+C stops the server.',flush=True)
    if args.open_browser:
        import webbrowser
        webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
