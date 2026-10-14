@echo off
if not exist "%~dp0project\setup.cmd" (
  echo Project entry point not found.
  exit /b 1
)
call "%~dp0project\setup.cmd" %*
exit /b %ERRORLEVEL%
