"""Bundle source and measured evidence, excluding environments, models and caches."""
import hashlib
import json
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent
output = root / "dist"
output.mkdir(exist_ok=True)
target = output / "local-research-stack-0.2.0.zip"
files = [root / name for name in ["README.md", "PERFORMANCE.md", "OCR-MODELS.md", "pyproject.toml", "uv.lock",
          "Dockerfile", "compose.yaml", ".dockerignore", ".gitignore", "server.py", "setup.ps1", "benchmark.ps1",
          "configure_mcp.py", "build_release.py"]]
files += list((root / "src").rglob("*.py")) + list((root / "tests").rglob("*.py"))
files += [p for p in (root/'services').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
files += [root/'ROUTER-V2.md',root/'results/router-v4-final-tests.log']
for run in ["release-2026-11-01", "controlled-first"]:
    files += [root / "results" / run / name for name in ["raw.json", "summary.json", "summary.md"]]
files += [root / "results" / name for name in ["mcp-final.json", "mcp-docker-final.json", "mcp-native-release.json",
                                               "docker-health.json", "unit-tests.log"]]
with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        if path.exists():
            archive.write(path, "local-research-stack/" + path.relative_to(root).as_posix())
manifest = {"file": target.name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "bytes": target.stat().st_size,
            "excluded": [".venv", ".cache", "model weights", "credentials", "novel files"]}
(output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps(manifest))
