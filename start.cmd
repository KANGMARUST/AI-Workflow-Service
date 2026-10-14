@echo off
if not exist "%~dp0project\start.cmd" (
  echo Project entry point not found.
  exit /b 1
)
call "%~dp0project\start.cmd" %*
exit /b %ERRORLEVEL%
