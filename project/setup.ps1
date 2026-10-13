param([string]$PythonPath = $env:QUOTE_PYTHON)
$ErrorActionPreference = 'Stop'
$projectPath = $PSScriptRoot
if (-not $PythonPath) {
    $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundledPython) { $PythonPath = $bundledPython }
    else { $PythonPath = 'python' }
}
Write-Host '백엔드 라이브러리를 설치합니다.'
& $PythonPath -m pip install --target (Join-Path $projectPath 'backend\.packages') -r (Join-Path $projectPath 'backend\requirements.txt')
if ($LASTEXITCODE -ne 0) { throw '백엔드 설치 실패. Python 3.11 이상과 네트워크 연결을 확인하세요.' }
Write-Host '프론트 라이브러리를 설치합니다.'
Push-Location (Join-Path $projectPath 'frontend')
try {
    if (Test-Path -LiteralPath 'package-lock.json') { npm.cmd ci }
    else { npm.cmd install }
    if ($LASTEXITCODE -ne 0) { throw '프론트 설치 실패. Node 24와 npm 11을 확인하세요.' }
} finally { Pop-Location }
Write-Host '설치 완료. .\start.ps1 로 실행하세요.'

