@echo off
setlocal
cd /d "%~dp0"
set "TARGET=%~dp0Abrir_Screen_Translate.bat"
set "DESKTOP=%USERPROFILE%\Desktop"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$W=New-Object -ComObject WScript.Shell; $S=$W.CreateShortcut([IO.Path]::Combine($env:USERPROFILE,'Desktop','Screen Translate.lnk')); $S.TargetPath=$env:TARGET; $S.WorkingDirectory='%~dp0'; $S.IconLocation='%SystemRoot%\System32\SHELL32.dll,44'; $S.Save()"
echo.
echo Atalho criado na area de trabalho.
pause
