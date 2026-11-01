import hashlib
import http.server
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent
ASSETS=ROOT/'public-assets'
ALLOWED={p.name:p for p in ASSETS.iterdir() if p.is_file() and p.suffix in {'.pdf','.html'}}

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        name=urlsplit(self.path).path.lstrip('/')
        if name not in ALLOWED:
            self.send_error(404)
            return
        path=ALLOWED[name]
        data=path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type','application/pdf' if path.suffix=='.pdf' else 'text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('ETag','"'+hashlib.sha256(data).hexdigest()+'"')
        # Disable intermediate HTTP caches; provider result caches are tested separately.
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(data)
        with (ROOT/'origin-requests.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps({'time':time.time(),'file':name,'user_agent':self.headers.get('User-Agent')})+'\n')
    def log_message(self,*args):
        pass

if __name__=='__main__':
    print('Serving only allowlisted synthetic documents on 127.0.0.1:8767',flush=True)
    http.server.ThreadingHTTPServer(('127.0.0.1',8767),Handler).serve_forever()
