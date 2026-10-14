@echo off
setlocal
set "QUOTE_CODEX_EXE=%LOCALAPPDATA%\Programs\OpenAI\Codex\bin\codex.exe"
if exist "%QUOTE_CODEX_EXE%" goto codex_ready
set "QUOTE_CODEX_EXE="
for /f "delims=" %%I in ('where.exe codex.exe 2^>nul') do if not defined QUOTE_CODEX_EXE set "QUOTE_CODEX_EXE=%%I"
if defined QUOTE_CODEX_EXE goto codex_ready
echo Codex CLI was not found. Install Codex CLI, then reopen CMD.
exit /b 1

:codex_ready
if not defined QUOTE_CODEX_WORKSPACE set "QUOTE_CODEX_WORKSPACE=%~dp0."
if not defined QUOTE_CODEX_MODEL set "QUOTE_CODEX_MODEL=gpt-6-sol"
set "QUOTE_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%QUOTE_PYTHON%" set "QUOTE_PYTHON=%~dp0backend\.venv\Scripts\python.exe"
if exist "%QUOTE_PYTHON%" for %%I in ("%QUOTE_PYTHON%") do set "PATH=%%~dpI;%PATH%"
set "QUOTE_NODE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
if exist "%QUOTE_NODE%" for %%I in ("%QUOTE_NODE%") do set "PATH=%%~dpI;%PATH%"
"%QUOTE_CODEX_EXE%" -c model="%QUOTE_CODEX_MODEL%" -c windows.sandbox=mxc --cd "%QUOTE_CODEX_WORKSPACE%" --sandbox workspace-write --ask-for-approval on-request --no-alt-screen %*
exit /b %ERRORLEVEL%
