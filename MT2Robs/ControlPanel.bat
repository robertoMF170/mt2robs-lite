@echo off
cd /d "%~dp0.."
where pythonw.exe >nul 2>&1
if %errorlevel%==0 ( start "" pythonw.exe "MT2Robs\ControlPanel.py" & exit /b )
where python.exe >nul 2>&1
if %errorlevel%==0 ( start "" python.exe "MT2Robs\ControlPanel.py" & exit /b )
py -3 "MT2Robs\ControlPanel.py"
