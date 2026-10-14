@echo off
if not exist "%~dp0project\stop.cmd" (
  echo Project entry point not found.
  exit /b 1
)
call "%~dp0project\stop.cmd" %*
exit /b %ERRORLEVEL%
