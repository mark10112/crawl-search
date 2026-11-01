import hashlib,json,zipfile
from pathlib import Path
root=Path(__file__).resolve().parent
target=root/'benchmark-evidence.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    for path in root.rglob('*'):
        if not path.is_file() or path==target or '__pycache__' in path.parts or path.name=='bundle-manifest.json':continue
        z.write(path,path.relative_to(root).as_posix())
out={'file':target.name,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
(root/'bundle-manifest.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out))
