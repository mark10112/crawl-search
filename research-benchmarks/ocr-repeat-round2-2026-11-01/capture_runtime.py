import hashlib,importlib.metadata as m,json,platform,sys
from pathlib import Path
out=Path(sys.argv[1])
packages={n:m.version(n) for n in ['paddleocr','paddlex','paddlepaddle','mlx-vlm','mlx','mlx-metal']}
base=Path(m.distribution('mlx-vlm').locate_file('mlx_vlm'))
files=['server/schemas.py','server/request_normalization.py','server/generation.py','generate/ar.py']
result={'packages':packages,'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),'model':'PaddlePaddle/PaddleOCR-VL-1.6','model_revision':'c5630abae1d940eafe0697512a0325494b02ab42','mlx_source_hashes':{f:hashlib.sha256((base/f).read_bytes()).hexdigest() for f in files}}
(out/'runtime.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
