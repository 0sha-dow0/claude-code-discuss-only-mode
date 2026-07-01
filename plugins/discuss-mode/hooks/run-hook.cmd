: << 'CMDBLOCK'
@echo off
REM Windows: run the named Python hook script with python, falling back to py.
REM Script name is passed WITHOUT extension so Claude Code's .sh/.py command
REM auto-detection does not interfere. Fails open (exit 0) so a hook error
REM never wedges the session.
python "%~dp0..\scripts\%~1.py" 2>nul || py "%~dp0..\scripts\%~1.py"
exit /b 0
CMDBLOCK
# Unix: run the named Python hook script with python3, falling back to python.
DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "${DIR}/../scripts/$1.py" 2>/dev/null || python "${DIR}/../scripts/$1.py"
exit 0
