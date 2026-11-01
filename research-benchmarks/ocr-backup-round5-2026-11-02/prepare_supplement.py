"""Preserve the first run and copy its frozen inputs for a CPU-only follow-up."""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).parent
BASE=Path.home()/'research-server/benchmarks'
SOURCE=BASE/'ocr-backup-round5-2026-11-02';WORK=BASE/'ocr-backup-round5-detector-2026-11-02'
assert (SOURCE/'restored.json').exists() and not WORK.exists()
WORK.mkdir();shutil.copytree(SOURCE/'inputs',WORK/'inputs')
for name in ['inputs.json','references.json','models.json']:shutil.copy2(SOURCE/name,WORK/name)
folder=Path.home()/'.paddlex/official_models/PP-OCRv5_mobile_det'
data={'model':'PP-OCRv5_mobile_det','files':[{'name':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(folder.iterdir()) if p.is_file()]}
(WORK/'detector-model.json').write_text(json.dumps(data,indent=2))
subprocess.run([str(Path.home()/'research-server/envs/ocr/bin/python'),str(HERE/'run_mac.py'),str(WORK)],env={**os.environ,'BACKUP_MODES':'paddle_mobile_ocr'},check=True)
