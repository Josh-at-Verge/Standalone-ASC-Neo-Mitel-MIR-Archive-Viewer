@echo off
setlocal DisableDelayedExpansion
title Call Archive Web Server
rem Place this file beside server.py and the dist folder.
rem Recordings always lives beside this batch file.
set "RECORDINGS=%~dp0Recordings"
set "ARCHIVE_PORT=8765"

pushd "%~dp0"
if errorlevel 1 goto directory_error
if not exist "server.py" goto missing_files
if not exist "dist\index.html" goto missing_files

set "PYRUN=py -3"
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if not errorlevel 1 goto python_ready
set "PYRUN=python"
python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 goto no_python

:python_ready
if not exist "%RECORDINGS%\." goto bad_folder
set "ARCHIVE_ROOT=%RECORDINGS%"
echo.
echo Starting http://127.0.0.1:%ARCHIVE_PORT%
echo The browser opens when the web server is ready.
echo Leave this window open while using the website.
echo Press Ctrl+C in this window to stop the server.
echo.
%PYRUN% -c "import os,sys,threading,time,json,urllib.request,webbrowser,runpy; from pathlib import Path; root=str(Path(os.environ['ARCHIVE_ROOT']).resolve()); port=os.environ['ARCHIVE_PORT']; url='http://127.0.0.1:'+port; exec('def open_when_ready():\n for attempt in range(120):\n  try:\n   with urllib.request.urlopen(url+\"/api/status\", timeout=1) as response: data=json.load(response)\n   if data.get(\"localArchive\") and data.get(\"root\")==root:\n    webbrowser.open(url); return\n  except Exception: pass\n  time.sleep(0.5)\n print(\"Browser did not open automatically. Open \"+url+\" manually.\", flush=True)'); threading.Thread(target=open_when_ready,daemon=True).start(); sys.argv=['server.py',root,'--port',port]; runpy.run_path('server.py',run_name='__main__')"
set "ARCHIVE_EXIT=%ERRORLEVEL%"
echo.
if "%ARCHIVE_EXIT%"=="0" goto stopped
echo The server exited with an error. Review the message above.
echo If port %ARCHIVE_PORT% is already in use, close the other server
echo or change ARCHIVE_PORT near the top of this BAT file.
goto finished

:stopped
echo Web server stopped.
goto finished

:missing_files
echo ERROR: Place this BAT file in the extracted Call_Archive folder,
echo beside server.py and the dist folder. Do not run it inside the ZIP.
goto finished

:no_python
echo ERROR: Python 3.10 or newer is required.
echo Install Python for Windows, enable its PATH option, then try again.
goto finished

:bad_folder
echo ERROR: The Recordings subfolder is missing or unavailable.
echo Create a folder named Recordings beside this BAT file,
echo then place your recording XML and WAV files inside it.
goto finished

:directory_error
echo ERROR: Cannot open the folder containing this BAT file.
pause
exit /b 1

:finished
echo.
pause
popd
endlocal
