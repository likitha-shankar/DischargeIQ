@echo off
REM DischargeIQ - one-command startup for Windows.
REM
REM What this does:
REM   1. Creates .venv if missing and installs requirements.txt.
REM   2. Verifies .env exists and that required API keys are non-empty.
REM      Exits with clear instructions if any required key is missing.
REM   3. Starts the FastAPI backend (uvicorn) on http://127.0.0.1:8000.
REM   4. Starts the Streamlit frontend on http://127.0.0.1:8501.
REM   5. Closing this window stops both servers.

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PY=python"
set "VENV_DIR=.venv"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=8501"

echo ------------------------------------------------------------
echo  DischargeIQ - startup
echo ------------------------------------------------------------

REM -- 1. Python check --------------------------------------------------
where %PY% >nul 2>&1
if errorlevel 1 (
    echo ERROR: '%PY%' not found on PATH. Install Python 3.11+ and retry.
    exit /b 1
)

for /f "delims=" %%V in ('%PY% -c "import sys; print(sys.version.split()[0])"') do set "PY_VERSION=%%V"
echo [start] Python: !PY_VERSION!

REM -- 2. Virtual env + deps --------------------------------------------
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [start] Creating virtual environment in %VENV_DIR%
    %PY% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo ERROR: failed to create virtual environment.
        exit /b 1
    )
)

call "%VENV_DIR%\Scripts\activate.bat"

echo [start] Installing requirements ^(quiet^)
pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    exit /b 1
)

REM -- 3. .env validation -----------------------------------------------
if not exist ".env" (
    if exist ".env.example" (
        copy /Y ".env.example" ".env" >nul
        echo.
        echo ============================================================
        echo  .env created from .env.example.
        echo.
        echo  ACTION REQUIRED - edit .env and fill in at minimum:
        echo    * ANTHROPIC_API_KEY   ^(Claude - used by Agents 2-5^)
        echo.
        echo  Depending on LLM_PROVIDER, also set ONE of:
        echo    * OPENROUTER_API_KEY  ^(if LLM_PROVIDER=openrouter, default^)
        echo    * OPENAI_API_KEY      ^(if LLM_PROVIDER=openai^)
        echo    * ^(nothing^)           ^(if LLM_PROVIDER=ollama^)
        echo.
        echo  Then re-run:  start.bat
        echo ============================================================
        exit /b 1
    ) else (
        echo ERROR: .env and .env.example both missing. Cannot continue.
        exit /b 1
    )
)

REM Read the required keys from .env via a small Python helper.
REM This handles quoting and trailing whitespace without a fragile .bat parser.
for /f "delims=" %%L in ('%PY% -c "from dotenv import dotenv_values; v=dotenv_values('.env'); import sys; sys.stdout.write('LLM_PROVIDER=%%s\nANTHROPIC=%%s\nOPENROUTER=%%s\nOPENAI=%%s' %% (v.get('LLM_PROVIDER','openrouter') or 'openrouter', v.get('ANTHROPIC_API_KEY','') or '', v.get('OPENROUTER_API_KEY','') or '', v.get('OPENAI_API_KEY','') or ''))"') do (
    for /f "tokens=1,2 delims==" %%A in ("%%L") do (
        set "%%A=%%B"
    )
)

set "MISSING="
if "!ANTHROPIC!"=="" set "MISSING=!MISSING! ANTHROPIC_API_KEY"

if /I "!LLM_PROVIDER!"=="openrouter" (
    if "!OPENROUTER!"=="" set "MISSING=!MISSING! OPENROUTER_API_KEY"
)
if /I "!LLM_PROVIDER!"=="openai" (
    if "!OPENAI!"=="" set "MISSING=!MISSING! OPENAI_API_KEY"
)

if not "!MISSING!"=="" (
    echo.
    echo ============================================================
    echo  .env is missing required values. Open .env and set:
    for %%K in (!MISSING!) do (
        echo    * %%K
    )
    echo.
    echo  Then re-run:  start.bat
    echo ============================================================
    exit /b 1
)

echo [start] .env OK  ^(LLM_PROVIDER=!LLM_PROVIDER!^)

REM -- 4. Launch servers ------------------------------------------------
if not exist "logs" mkdir "logs"

echo [start] Backend  -^> http://127.0.0.1:%BACKEND_PORT%  ^(log: logs\backend.log^)
start "DischargeIQ backend" /b cmd /c "uvicorn dischargeiq.main:app --host 127.0.0.1 --port %BACKEND_PORT% --reload > logs\backend.log 2>&1"

echo [start] Frontend -^> http://127.0.0.1:%FRONTEND_PORT% ^(log: logs\frontend.log^)
echo.
echo [start] Both servers running. Close this window or press Ctrl-C to stop.
echo [start] Open: http://127.0.0.1:%FRONTEND_PORT%

REM --server.headless true skips Streamlit's first-run email prompt
REM (which blocks on redirected stdin) and stops the auto-browser-open.
streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port %FRONTEND_PORT% --server.headless true --browser.gatherUsageStats false

REM When streamlit exits (Ctrl-C), kill the backend too.
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":%BACKEND_PORT% " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%P >nul 2>&1
)

endlocal
