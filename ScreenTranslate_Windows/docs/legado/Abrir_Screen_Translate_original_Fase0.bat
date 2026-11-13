@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Screen Translate PC

cd /d "%~dp0"

echo.
echo  ==========================================
echo       SCREEN TRANSLATE PC - Inicializador
echo  ==========================================
echo.

where py >nul 2>&1
if %errorlevel%==0 (
    set "PY=py"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set "PY=python"
    ) else (
        echo [ERRO] Python nao foi encontrado.
        echo Instale o Python 3.10+ e marque "Add Python to PATH".
        echo.
        pause
        exit /b 1
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Criando ambiente isolado do programa...
    %PY% -m venv .venv
    if errorlevel 1 goto :venv_error
)

set "VPY=%~dp0.venv\Scripts\python.exe"

echo [2/3] Verificando componentes...
"%VPY%" -c "import PyQt5, mss, numpy, rapidocr_onnxruntime, argostranslate" >nul 2>&1
if errorlevel 1 (
    echo Instalando componentes necessarios. Isso acontece apenas na primeira vez.
    "%VPY%" -m pip install --upgrade pip
    "%VPY%" -m pip install -r requirements.txt
    if errorlevel 1 goto :install_error
)

"%VPY%" -c "import argostranslate.translate as t; a=t.get_installed_languages(); f=next((x for x in a if x.code=='en'),None); q=next((x for x in a if x.code=='pt'),None); assert f and q and f.get_translation(q)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo O pacote de traducao INGLÊS ^> PORTUGUES ainda nao esta instalado.
    echo Ele sera baixado uma unica vez e depois funcionara offline.
    echo.
    choice /C SN /N /M "Instalar agora? [S/N]: "
    if errorlevel 2 goto :launch
    if errorlevel 1 (
        "%VPY%" install_language_pack.py en pt
        if errorlevel 1 goto :lang_error
    )
)

:launch
echo.
echo [3/3] Abrindo o Screen Translate...
echo.
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
exit /b 0

:venv_error
echo.
echo [ERRO] Nao foi possivel criar o ambiente do programa.
pause
exit /b 1

:install_error
echo.
echo [ERRO] Falha ao instalar os componentes.
echo Verifique sua internet e tente abrir este arquivo novamente.
pause
exit /b 1

:lang_error
echo.
echo [ERRO] Nao foi possivel instalar o pacote de traducao EN ^> PT.
echo Verifique sua internet e tente novamente.
pause
exit /b 1
