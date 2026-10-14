@echo off
setlocal
set "QUOTE_CODEX_WORKSPACE=%~dp0."
if not exist "%~dp0project\codex.cmd" (
  echo Project entry point not found.
  exit /b 1
)
call "%~dp0project\codex.cmd" %*
exit /b %ERRORLEVEL%
