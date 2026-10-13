param([string]$PythonPath = $env:QUOTE_PYTHON)
$ErrorActionPreference = 'Stop'
$projectPath = $PSScriptRoot
$runtimePath = Join-Path $projectPath '.runtime'
New-Item -ItemType Directory -Force -Path $runtimePath | Out-Null
if (-not $PythonPath) {
    $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundledPython) { $PythonPath = $bundledPython }
    else { $PythonPath = (Get-Command python -ErrorAction Stop).Source }
}
if (-not (Test-Path -LiteralPath (Join-Path $projectPath 'frontend\node_modules'))) {
    throw '라이브러리를 먼저 설치하세요: .\setup.ps1'
}
$backendReady = $false
try { $backendReady = (Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2).ok } catch {}
if (-not $backendReady) {
    $backendEntry = Join-Path $projectPath 'backend\run.py'
    $backendProcess = Start-Process -FilePath $PythonPath -ArgumentList ('"' + $backendEntry + '"') -WorkingDirectory (Join-Path $projectPath 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimePath 'backend.log') -RedirectStandardError (Join-Path $runtimePath 'backend-error.log')
    $backendProcess.Id | Set-Content -LiteralPath (Join-Path $runtimePath 'backend.pid')
}
$frontendReady = $false
try { $frontendReady = (Invoke-WebRequest 'http://127.0.0.1:5173' -TimeoutSec 2).StatusCode -eq 200 } catch {}
if (-not $frontendReady) {
    $nodePath = (Get-Command node -ErrorAction Stop).Source
    $viteEntry = Join-Path $projectPath 'frontend\node_modules\vite\bin\vite.js'
    $frontendProcess = Start-Process -FilePath $nodePath -ArgumentList @(('"' + $viteEntry + '"'),'--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory (Join-Path $projectPath 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimePath 'frontend.log') -RedirectStandardError (Join-Path $runtimePath 'frontend-error.log')
    $frontendProcess.Id | Set-Content -LiteralPath (Join-Path $runtimePath 'frontend.pid')
}
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $apiCheck = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
        $webCheck = Invoke-WebRequest 'http://127.0.0.1:5173' -TimeoutSec 2
        if ($apiCheck.ok -and $webCheck.StatusCode -eq 200) {
            Write-Host '실행 완료: http://127.0.0.1:5173'
            Write-Host '원본은 샘플 불러오기에서 등록합니다. 종료는 .\stop.ps1 입니다.'
            exit 0
        }
    } catch {}
    Start-Sleep -Seconds 1
}
throw '서버가 준비되지 않았습니다. .runtime 로그를 확인하세요.'

