import hashlib
import json
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent
output = root/'dist'
output.mkdir(exist_ok=True)
target = output/'ocr-multilingual-benchmark-2026-11-01.zip'
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
    for path in root.rglob('*'):
        if path.is_file() and not any(part in {'dist','__pycache__','.git'} for part in path.relative_to(root).parts):
            archive.write(path,'ocr-multilingual-benchmark/'+path.relative_to(root).as_posix())
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
manifest = {'file':target.name,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
            'includes':'source, dataset, references, raw outputs, timing/memory data, logs and report',
            'excludes':'Docker images and model weights (retained locally in Docker cache/volume)'}
(output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest))
