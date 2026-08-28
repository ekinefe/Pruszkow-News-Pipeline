@echo off
echo =========================================
echo   Pruszkow News Pipeline - First Setup
echo =========================================
echo.

cd /d "%~dp0"

:: --- Check Python ---
where python >nul 2>nul
if %errorlevel% neq 0 (
    where python3 >nul 2>nul
    if %errorlevel% neq 0 (
        echo [ERROR] Python not found. Install Python 3.10+ first.
        pause
        exit /b 1
    )
    set PYTHON=python3
) else (
    set PYTHON=python
)
echo [OK] Python found

:: --- Create .env from example if missing ---
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [OK] Created .env from .env.example
    ) else (
        echo [WARN] No .env.example found. Creating minimal .env...
        (
            echo HOST=0.0.0.0
            echo PORT=8000
            echo GMAIL_CREDENTIALS_FILE=client_secret.json
            echo AI_PROVIDER=gemini
            echo GEMINI_API_KEY=
            echo CLAUDE_API_KEY=
            echo OPENAI_API_KEY=
        ) > .env
        echo [OK] Created minimal .env
    )
) else (
    echo [OK] .env exists
)

:: --- Check if API keys are configured ---
set NEEDS_SETUP=0
findstr /C:"GEMINI_API_KEY=" .env | findstr /v /C:"GEMINI_API_KEY= " >nul 2>nul
if %errorlevel%==0 (
    findstr /C:"CLAUDE_API_KEY=" .env | findstr /v /C:"CLAUDE_API_KEY= " >nul 2>nul
    if %errorlevel%==0 (
        findstr /C:"OPENAI_API_KEY=" .env | findstr /v /C:"OPENAI_API_KEY= " >nul 2>nul
        if %errorlevel%==0 (
            set NEEDS_SETUP=1
        )
    )
)

if %NEEDS_SETUP%==1 (
    echo.
    echo --- First-Time Setup ---
    echo No API keys found. Let's configure your AI provider.
    echo.
    echo Select AI provider:
    echo   1) Google Gemini ^(recommended, free tier available^)
    echo   2) Anthropic Claude
    echo   3) OpenAI
    echo.
    echo Press ENTER to skip and add your API key later in the Settings ^(UI^).
    echo.
    set /p PROVIDER_CHOICE="Choice [1]: "
    if "%PROVIDER_CHOICE%"=="" set PROVIDER_CHOICE=1

    if "%PROVIDER_CHOICE%"=="1" (
        set PROVIDER=gemini
        echo.
        echo Get your key at: https://aistudio.google.com/apikey
        set /p API_KEY="Gemini API Key: "
        if not "%API_KEY%"=="" (
            powershell -Command "(Get-Content .env) -replace '^GEMINI_API_KEY=.*', 'GEMINI_API_KEY=%API_KEY%' | Set-Content .env"
        )
    ) else if "%PROVIDER_CHOICE%"=="2" (
        set PROVIDER=claude
        echo.
        echo Get your key at: https://console.anthropic.com/
        set /p API_KEY="Claude API Key: "
        if not "%API_KEY%"=="" (
            powershell -Command "(Get-Content .env) -replace '^CLAUDE_API_KEY=.*', 'CLAUDE_API_KEY=%API_KEY%' | Set-Content .env"
        )
    ) else (
        set PROVIDER=openai
        echo.
        echo Get your key at: https://platform.openai.com/api-keys
        set /p API_KEY="OpenAI API Key: "
        if not "%API_KEY%"=="" (
            powershell -Command "(Get-Content .env) -replace '^OPENAI_API_KEY=.*', 'OPENAI_API_KEY=%API_KEY%' | Set-Content .env"
        )
    )

    powershell -Command "(Get-Content .env) -replace '^AI_PROVIDER=.*', 'AI_PROVIDER=%PROVIDER%' | Set-Content .env"
    if not "%API_KEY%"=="" (
        echo [OK] API key configured for %PROVIDER%
    ) else (
        echo [OK] Provider set to %PROVIDER%. API key skipped - add it in the Settings page ^(UI^).
    )
) else (
    echo [OK] API keys found
)

:: --- Check Gmail credentials ---
if exist "client_secret.json" (
    echo [OK] Gmail credentials found
) else (
    echo [WARN] Gmail credentials not found: client_secret.json
    echo        Download from: https://console.cloud.google.com/apis/credentials
)

:: --- Check Gmail token ---
if exist "token.json" (
    echo [OK] Gmail token found ^(authenticated^)
) else (
    echo [INFO] Gmail not yet authenticated. Connect via Settings page after startup.
)

:: --- Create data directories ---
if not exist "data\articles" mkdir "data\articles"
if not exist "data\attachments" mkdir "data\attachments"
echo [OK] Data directories ready

:: --- Create virtual environment ---
if not exist "venv" (
    echo Creating virtual environment...
    %PYTHON% -m venv venv
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment exists
)

:: --- Activate venv ---
call venv\Scripts\activate.bat

:: --- Install dependencies ---
echo Checking dependencies...
pip install -q -r requirements.txt
echo [OK] Dependencies installed

:: --- Ask for port ---
echo.
set /p INPUT_PORT="Enter port number (default 8000): "
if "%INPUT_PORT%"=="" set INPUT_PORT=8000

:: --- Update port in .env ---
powershell -Command "(Get-Content .env) -replace '^PORT=.*', 'PORT=%INPUT_PORT%' | Set-Content .env"

echo.
echo =========================================
echo   Server starting at http://localhost:%INPUT_PORT%
echo   Press Ctrl+C to stop
echo =========================================
echo.

uvicorn backend.main:app --host 0.0.0.0 --port %INPUT_PORT% --reload
