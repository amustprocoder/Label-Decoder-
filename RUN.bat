@echo off
cd /d "%~dp0"
echo ============================================
echo   Indian Label Decoder
echo ============================================
echo.
echo Photo / text input needs a model key. Barcode and Examples tabs work without one.
echo   Free key:  https://aistudio.google.com/apikey   (Gemini)
echo   Or Claude: https://console.anthropic.com         (ANTHROPIC_API_KEY)
echo Key is used for this run only and never saved.
echo.
set /p GEMINI_API_KEY=Paste a Gemini key and press Enter (or just Enter to skip):
if "%GEMINI_API_KEY%"=="" set GEMINI_API_KEY=
echo.
pip install -q -r requirements.txt
set PYTHONIOENCODING=utf-8
streamlit run app.py
pause
