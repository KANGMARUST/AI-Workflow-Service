@echo off
setlocal
where node >nul 2>&1
if errorlevel 1 (
  if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" (
    "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" "%~dp0launcher.mjs" start
    exit /b
  )
  echo Node.js 24 is required. Install Node.js and reopen this terminal.
  exit /b 1
)
node "%~dp0launcher.mjs" start
exit /b %errorlevel%
