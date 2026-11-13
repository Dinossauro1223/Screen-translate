@echo off
setlocal EnableExtensions
rem Cria o atalho Screen Translate na Area de Trabalho. Logica em Python: python -m bootstrap atalho.
rem Arquivo somente ASCII e com fim de linha CRLF.
cd /d "%~dp0"
if not exist "logs" mkdir "logs"
echo [%date% %time%] criar atalho >> "%~dp0logs\launcher.log"
py -3.12 --version >> "%~dp0logs\launcher.log" 2>&1
if errorlevel 1 goto :sem_py312
py -3.12 -m bootstrap atalho
goto :resultado

:sem_py312
python -m bootstrap atalho

:resultado
if errorlevel 1 goto :falhou
echo.
echo Atalho criado. Confira a Area de Trabalho.
exit /b 0

:falhou
echo.
echo Nao foi possivel criar o atalho. Veja os detalhes nos arquivos da pasta logs: launcher.log e bootstrap-*.log
pause
exit /b 1
