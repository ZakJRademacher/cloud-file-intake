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

ROOT=Path(__file__).resolve().parents[1]
SAMPLES={'weekly-sales.csv','alternate-headers.csv','bad-schema.csv'}


def make_handler(store, token):
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
    args=parser.parse_args()
    store=LocalStore(args.store)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(store,secrets.token_urlsafe(32)))
    url=f'http://127.0.0.1:{server.server_port}/'
    print(f'Cloud File Intake — LOCAL ONLY\n{url}\nStore: {store.root}\nCtrl+C stops the server.',flush=True)
    if args.open_browser:
        import webbrowser
        webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
