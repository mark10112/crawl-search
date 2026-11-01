"""Single-worker durable ledger. Documents and results stay on the server."""
import hashlib,json,sqlite3,time,uuid
from pathlib import Path

class JobStore:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.uploads=self.root/'uploads';self.uploads.mkdir(exist_ok=True)
        self.db=sqlite3.connect(self.root/'jobs.sqlite3');self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY,status TEXT,args TEXT,result TEXT,created REAL,updated REAL,attempts INTEGER DEFAULT 0)');self.db.commit()
    def recover(self):
        self.db.execute("UPDATE jobs SET status=CASE WHEN attempts<3 THEN 'queued' ELSE 'failed' END,updated=? WHERE status='running'",(time.time(),));self.db.commit()
    def submit(self,args):
        if self.db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]>=32:raise ValueError('Queue full')
        ident=uuid.uuid4().hex;now=time.time()
        self.db.execute('INSERT INTO jobs(id,status,args,created,updated) VALUES(?,?,?,?,?)',(ident,'queued',json.dumps(args),now,now));self.db.commit();return self.get(ident)
    def get(self,ident):
        row=self.db.execute('SELECT * FROM jobs WHERE id=?',(ident,)).fetchone()
        if not row:return None
        item=dict(row);item['arguments']=json.loads(item.pop('args'));item['result']=json.loads(item['result']) if item['result'] else None;return item
    def claim(self):
        row=self.db.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
        if not row:return None
        self.db.execute("UPDATE jobs SET status='running',attempts=attempts+1,updated=? WHERE id=?",(time.time(),row['id']));self.db.commit();return self.get(row['id'])
    def counts(self):
        return {row['status']:row['n'] for row in self.db.execute('SELECT status,COUNT(*) AS n FROM jobs GROUP BY status')}
    def finish(self,ident,result):
        self.db.execute('UPDATE jobs SET status=?,result=?,updated=? WHERE id=?',('complete' if result.get('ok') else 'failed',json.dumps(result,ensure_ascii=False),time.time(),ident));self.db.commit()
    def upload(self,data):
        if not data or len(data)>32*1024*1024:raise ValueError('Upload must be 1 byte to 32 MiB')
        if not data.startswith((b'%PDF',b'\x89PNG',b'\xff\xd8\xff',b'II*\x00',b'MM\x00*')):raise ValueError('Only PDF, PNG, JPEG or TIFF')
        ident=hashlib.sha256(data).hexdigest();path=self.uploads/ident
        if not path.exists():path.write_bytes(data)
        return {'upload_id':ident,'bytes':len(data),'sha256':ident}
    def asset(self,ident):
        if len(ident)!=64 or any(c not in '0123456789abcdef' for c in ident):raise ValueError('Invalid upload ID')
        path=self.uploads/ident
        if not path.is_file():raise ValueError('Unknown upload ID')
        return path
    def close(self):self.db.close()
