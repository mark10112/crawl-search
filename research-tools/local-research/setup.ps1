param([switch]$WithDocling)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $syncArguments = @('sync', '--frozen', '--extra', 'browser')
    if ($WithDocling) { $syncArguments += @('--extra', 'ocr') }
    & uv @syncArguments
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
    & '.\.venv\Scripts\python.exe' -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw 'Browser installation failed' }
    $languageDirectory = Join-Path $PSScriptRoot '.cache\tessdata'
    New-Item -ItemType Directory -Force -Path $languageDirectory | Out-Null
    foreach ($language in @('eng', 'tha')) {
        $target = Join-Path $languageDirectory "$language.traineddata"
        if (-not (Test-Path -LiteralPath $target)) {
            Invoke-WebRequest "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/$language.traineddata" -OutFile $target
        }
    }
    & '.\.venv\Scripts\python.exe' -m local_research.cli health
} finally { Pop-Location }
