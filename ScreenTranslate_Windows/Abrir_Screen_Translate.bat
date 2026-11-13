@echo off
setlocal EnableExtensions
rem Launcher minimo do Screen Translate. Toda a logica esta em Python: python -m bootstrap.
rem Arquivo somente ASCII e com fim de linha CRLF. Nao edite com programas que mudem isso.
cd /d "%~dp0"
if not exist "logs" mkdir "logs"
echo [%date% %time%] launcher iniciado em "%~dp0" >> "%~dp0logs\launcher.log"

py -3.12 --version >> "%~dp0logs\launcher.log" 2>&1
if errorlevel 1 goto :sem_py312
py -3.12 -m bootstrap %*
set "CODIGO=%errorlevel%"
goto :fim

:sem_py312
echo [%date% %time%] py -3.12 indisponivel; tentando o python do PATH >> "%~dp0logs\launcher.log"
python --version >> "%~dp0logs\launcher.log" 2>&1
if errorlevel 1 goto :sem_python
python -m bootstrap %*
set "CODIGO=%errorlevel%"
goto :fim

:sem_python
echo.
echo Nao encontrei o Python. Instale o Python 3.12 de 64 bits: https://www.python.org/downloads/windows/
echo Marque a opcao "Add python.exe to PATH" e deixe o launcher py marcado. Depois abra este arquivo de novo.
echo [%date% %time%] Python nao encontrado >> "%~dp0logs\launcher.log"
set "CODIGO=9"
goto :fim

:fim
echo [%date% %time%] launcher terminou com codigo %CODIGO% >> "%~dp0logs\launcher.log"
if "%CODIGO%"=="0" exit /b 0
echo.
echo O programa terminou com o codigo %CODIGO%. Veja os arquivos da pasta logs: launcher.log e bootstrap-*.log
pause
exit /b %CODIGO%
