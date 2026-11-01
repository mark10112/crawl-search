"""Document visual corrections transparently; preserve the pre-run reference lock."""
import hashlib,json,shutil,time
from pathlib import Path
root=Path(__file__).resolve().parent
source=root/'references.json';original=root/'references-original.json'
if original.exists():raise RuntimeError('Reference audit already applied')
shutil.copyfile(source,original)
data=json.loads(source.read_text(encoding='utf-8'))
changes=[]
for anchor in data['anchors']:
    before=anchor['text']
    if anchor['id']=='g2-bottom':anchor['text']=before.replace('การนั่งขาว','การนุ่งขาว')
    if anchor['id']=='g3-top':anchor['text']=before.replace('ความจำแล','ความเจ้าแล')
    if anchor['text']!=before:changes.append({'id':anchor['id'],'before':before,'after':anchor['text']})
for row in data['table_rows']:
    before=row['label']
    if row['document']=='thai-gazette' and row['label'].startswith('ประกาศให้ใช้'):
        row['label']='ประกาศให้ใช้กะแปะอัฐแลโสฬศที่ทำขึ้นใหม่'
        changes.append({'id':'table-g2-31','before':before,'after':row['label']})
source.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'reference-audit.json').write_text(json.dumps({'time':time.time(),'changes':changes,'reason':'Three transcription corrections after checking source at 4x; first provider outputs had already been seen. Original retained for sensitivity analysis; never changed source bytes or reader requests.',
    'original_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'amended_sha256':hashlib.sha256(source.read_bytes()).hexdigest()},ensure_ascii=False,indent=2),encoding='utf-8')
