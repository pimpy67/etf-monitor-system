@echo off
cd /d "%~dp0"
echo.
echo ================================================
echo   ANALISI PORTAFOGLIO ETF e BTP
echo ================================================
echo.

REM Cerca Python con xlrd: prima venv monitoraggio-fondi, poi sistema
set PYTHON=
if exist "..\monitoraggio-fondi\.venv\Scripts\python.exe" (
    set PYTHON="..\monitoraggio-fondi\.venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if %ERRORLEVEL%==0 set PYTHON=python
)

if "%PYTHON%"=="" (
    echo ERRORE: Python non trovato.
    echo Installa Python oppure assicurati che il venv monitoraggio-fondi esista.
    pause
    exit /b 1
)

%PYTHON% portfolio_analysis.py

echo.
if %ERRORLEVEL% NEQ 0 (
    echo ERRORE durante l'analisi. Premi un tasto per chiudere.
) else (
    echo Completato. Premi un tasto per chiudere.
)
pause
