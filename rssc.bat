@echo off
rem Windows launcher for Ruby Shell Script.
rem Usage:  rssc script.rss [args...]
rem         rssc -e "puts 1 + 1"
rem         rssc                 (starts the REPL)
setlocal
set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%rssc" %*
if errorlevel 9009 (
    py "%SCRIPT_DIR%rssc" %*
)
endlocal
