import argparse,hashlib,http.server,json,time
from pathlib import Path
from urllib.parse import urlsplit
p=argparse.ArgumentParser();p.add_argument('assets',type=Path);p.add_argument('log',type=Path);args=p.parse_args()
names=['thai-gazette.pdf','thai-royal.pdf','us-census.pdf','us-preservation.pdf']
allowed={n:args.assets/n for n in names}
class Handler(http.server.BaseHTTPRequestHandler):
    def respond(self,body):
        name=urlsplit(self.path).path.lstrip('/')
        if name not in allowed:self.send_error(404);return
        data=allowed[name].read_bytes()
        self.send_response(200);self.send_header('Content-Type','application/pdf');self.send_header('Content-Length',str(len(data)))
        self.send_header('ETag','"'+hashlib.sha256(data).hexdigest()+'"');self.send_header('Cache-Control','no-store');self.end_headers()
        if body:
            with args.log.open('a') as f:f.write(json.dumps({'time':time.time(),'file':name,'method':'GET','user_agent':self.headers.get('User-Agent')})+'\n')
            try:self.wfile.write(data)
            except BrokenPipeError:pass
    def do_GET(self):self.respond(True)
    def do_HEAD(self):self.respond(False)
    def log_message(self,*args):pass
http.server.ThreadingHTTPServer(('127.0.0.1',8877),Handler).serve_forever()
