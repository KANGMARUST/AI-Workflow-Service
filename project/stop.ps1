$ErrorActionPreference = 'Stop'
foreach ($serviceName in @('frontend','backend')) {
    $pidFile = Join-Path $PSScriptRoot ('.runtime\' + $serviceName + '.pid')
    if (Test-Path -LiteralPath $pidFile) {
        $savedProcessId = [int](Get-Content -LiteralPath $pidFile)
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$savedProcessId"
        $expected = if ($serviceName -eq 'frontend') { 'vite' } else { 'run.py' }
        if ($processInfo -and $processInfo.CommandLine -like ('*' + $expected + '*') -and $processInfo.CommandLine.IndexOf($PSScriptRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
            Stop-Process -Id $savedProcessId -ErrorAction SilentlyContinue
            Write-Host "$serviceName 종료 완료"
        }
        Remove-Item -LiteralPath $pidFile
    }
}

