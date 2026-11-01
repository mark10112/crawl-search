import hashlib,json,zipfile
from pathlib import Path
root=Path(__file__).resolve().parent
target=root/'real-history-evidence.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in root.rglob('*'):
        if not path.is_file() or path==target:continue
        relative=path.relative_to(root)
        if any(part in {'.deps','__pycache__'} for part in relative.parts):continue
        if relative.parts[0]=='sources' and path.suffix=='.pdf':continue
        if relative.parts[0]=='review' and '-selected-' in path.name:continue
        if path.name in {'bundle-manifest.json','tunnel.log'}:continue
        archive.write(path,relative.as_posix())
out={'file':target.name,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
     'excluded':['full original PDFs (available locally in sources/; URLs and hashes included)','model weights','Python dependencies','.venv','credentials','novel files','redundant full-page renders']}
(root/'bundle-manifest.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out))
