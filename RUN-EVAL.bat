@echo off
cd /d "%~dp0"
echo ============================================
echo   Label Decoder - evaluation run
echo ============================================
echo.
echo Step 1 (no key): pulls 100 Indian products + photos from Open Food Facts.
echo Step 2 (needs key): runs the vision model on the photos and scores accuracy.
echo   Free key: https://aistudio.google.com/apikey
echo.
set PYTHONIOENCODING=utf-8
if not exist eval\data\testset.jsonl python eval\build_testset.py --n 100
set /p GEMINI_API_KEY=Paste a Gemini key and press Enter (Enter = rules-layer only):
if "%GEMINI_API_KEY%"=="" (
    python eval\run_eval.py --rules-only
) else (
    echo --- first 20 products (2-3 min) ---
    python eval\run_eval.py --limit 20
    set /p FULL=Run all 100? (Y/N):
    if /i "%FULL%"=="Y" python eval\run_eval.py
)
echo.
echo Report: eval\results\report.md
pause
