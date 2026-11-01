param([ValidateSet('controlled','live','all')][string]$Suite='all', [int]$Repeats=3)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $env:PYTHONIOENCODING = 'utf-8'
    $env:LOCAL_RESEARCH_TESSDATA = Join-Path $PSScriptRoot '.cache\tessdata'
    $benchmarkOutput = 'results/run-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
    & '.\.venv\Scripts\python.exe' -m local_research.benchmark --suite $Suite --repeats $Repeats --real-pdf --output $benchmarkOutput
    if ($LASTEXITCODE -ne 0) { throw 'Benchmark did not complete; inspect partial raw.json' }
} finally { Pop-Location }
