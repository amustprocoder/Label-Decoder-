@echo off
cd /d "%~dp0"
echo ============================================
echo   Indian Label Decoder
echo ============================================
echo.
echo   1 = The website. Same as the Netlify link. (opens by itself in 8 seconds)
echo   2 = The photo app. Upload a pack photo and the AI reads it.
echo.
choice /c 12 /n /t 8 /d 1 /m "Press 1 or 2: "
if errorlevel 255 goto site
if errorlevel 2 goto app

:site
if exist "site\index.html" goto opensite
echo The website has not been built on this computer yet. Building it once...
pip install -q -r requirements.txt
set PYTHONIOENCODING=utf-8
python build_static.py
:opensite
echo Opening the website in your browser...
start "" "site\index.html"
exit /b

:app
echo.
echo Photo / text input needs a model key. Packs, barcode and face-off work without one.
echo   Free key:  https://aistudio.google.com/apikey   (Gemini)
echo   Or Claude: https://console.anthropic.com         (ANTHROPIC_API_KEY)
echo.
if defined GEMINI_API_KEY goto havekey
if defined ANTHROPIC_API_KEY goto havekey
echo No saved key found. A key pasted here is used for this run only.
echo To save it for good, run this once in a terminal, then open a new window:
echo     setx GEMINI_API_KEY "your-key"
echo.
set /p GEMINI_API_KEY=Paste a Gemini key and press Enter (or just Enter to skip):
goto run
:havekey
echo A saved key was found on this computer. Photo reading is on.
:run
echo.
pip install -q -r requirements.txt
set PYTHONIOENCODING=utf-8
streamlit run app.py
pause
