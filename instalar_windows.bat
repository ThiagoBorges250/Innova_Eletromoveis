@echo off
chcp 65001 >nul
echo ==========================================
echo  Instalacao - INNOVA Eletromoveis
echo ==========================================
py -m venv .venv
if errorlevel 1 (
 echo Erro: instale o Python e reinicie o terminal.
 pause
 exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if errorlevel 1 (
 echo Erro ao instalar bibliotecas. Confira a internet.
 pause
 exit /b 1
)
if not exist .env copy .env.example .env >nul
echo.
echo Pronto! Edite o arquivo .env com as credenciais e a chave secreta.
echo Depois execute iniciar_windows.bat.
pause
