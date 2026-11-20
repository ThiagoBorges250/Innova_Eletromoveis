@echo off
chcp 65001 >nul
if not exist .venv\Scripts\python.exe (
 echo Ambiente ausente. Execute instalar_windows.bat primeiro.
 pause
 exit /b 1
)
.venv\Scripts\python.exe app.py
pause
