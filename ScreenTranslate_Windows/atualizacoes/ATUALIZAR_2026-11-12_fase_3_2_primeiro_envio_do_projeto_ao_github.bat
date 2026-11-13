@echo off
setlocal EnableExtensions
rem Arquivo somente ASCII e com fim de linha CRLF (gerado por tools/gerar_atualizacao.py).
rem ====================================================================
rem Screen Translate Windows - atualizacao do GitHub
rem Data da atualizacao: 12/11/2026
rem Titulo: Fase 3.2 primeiro envio do projeto ao GitHub
rem O que esta atualizacao traz:
rem   - Projeto completo das Fases 0 a 3.2 na main do repositorio codigo, testes, documentos e guias
rem   - Fase 3.2: a traducao fica fora da captura da tela SetWindowDisplayAffinity e o programa testa isso sozinho ao abrir
rem   - Fase 3.2: a traducao antiga some na hora em que a tela muda e so le de novo 1,5 s depois de a tela parar
rem   - Fase 3.2: ruido, cursor e animacoes pequenas deixam de refazer o OCR; cache de traducoes
rem   - Repositorio: .gitignore, .gitattributes, gerador de .bat tools/gerar_atualizacao.py e este historico de atualizacoes
rem   - Nao verificado no Windows: o teste A/B do overlay e o plano B ainda precisam rodar no seu computador
rem ====================================================================
cd /d "%~dp0.."
set "REPO=https://github.com/Dinossauro1223/Screen-translate.git"
set "CODIGO=0"
if not exist "logs" mkdir "logs"
set "LOG=%CD%\logs\atualizacao.log"
echo [%date% %time%] atualizacao de 12/11/2026: Fase 3.2 primeiro envio do projeto ao GitHub >> "%LOG%"

echo.
echo Screen Translate - atualizacao de 12/11/2026
echo Fase 3.2 primeiro envio do projeto ao GitHub
echo.
echo O que esta atualizacao traz:
echo   - Projeto completo das Fases 0 a 3.2 na main do repositorio codigo, testes, documentos e guias
echo   - Fase 3.2: a traducao fica fora da captura da tela SetWindowDisplayAffinity e o programa testa isso sozinho ao abrir
echo   - Fase 3.2: a traducao antiga some na hora em que a tela muda e so le de novo 1,5 s depois de a tela parar
echo   - Fase 3.2: ruido, cursor e animacoes pequenas deixam de refazer o OCR; cache de traducoes
echo   - Repositorio: .gitignore, .gitattributes, gerador de .bat tools/gerar_atualizacao.py e este historico de atualizacoes
echo   - Nao verificado no Windows: o teste A/B do overlay e o plano B ainda precisam rodar no seu computador
echo.

where git >nul 2>&1
if errorlevel 1 goto :sem_git

if exist ".git" goto :repo_ok
echo Criando o repositorio local...
git init >> "%LOG%" 2>&1
if errorlevel 1 goto :falha
git symbolic-ref HEAD refs/heads/main >> "%LOG%" 2>&1
:repo_ok

git remote get-url origin >nul 2>&1
if errorlevel 1 goto :remoto_novo
git remote set-url origin "%REPO%" >> "%LOG%" 2>&1
goto :remoto_pronto
:remoto_novo
git remote add origin "%REPO%" >> "%LOG%" 2>&1
:remoto_pronto
if errorlevel 1 goto :falha

git config user.name >nul 2>&1
if errorlevel 1 git config user.name "Dinossauro1223"
git config user.email >nul 2>&1
if errorlevel 1 git config user.email "Dinossauro1223@users.noreply.github.com"

echo Preparando os arquivos...
git add -A >> "%LOG%" 2>&1
if errorlevel 1 goto :falha
git diff --cached --quiet
if not errorlevel 1 goto :sem_mudancas
git commit -m "[2026-11-12] Fase 3.2 primeiro envio do projeto ao GitHub" -m "- Projeto completo das Fases 0 a 3.2 na main do repositorio codigo, testes, documentos e guias" -m "- Fase 3.2: a traducao fica fora da captura da tela SetWindowDisplayAffinity e o programa testa isso sozinho ao abrir" -m "- Fase 3.2: a traducao antiga some na hora em que a tela muda e so le de novo 1,5 s depois de a tela parar" -m "- Fase 3.2: ruido, cursor e animacoes pequenas deixam de refazer o OCR; cache de traducoes" -m "- Repositorio: .gitignore, .gitattributes, gerador de .bat tools/gerar_atualizacao.py e este historico de atualizacoes" -m "- Nao verificado no Windows: o teste A/B do overlay e o plano B ainda precisam rodar no seu computador" >> "%LOG%" 2>&1
if errorlevel 1 goto :falha
:sem_mudancas

git branch -M main >> "%LOG%" 2>&1
echo.
echo Enviando para o GitHub. Na primeira vez o Windows pode abrir uma janela para voce entrar na sua conta.
git push -u origin main
if errorlevel 1 goto :falha_envio
echo.
echo Pronto. Atualizacao enviada para %REPO%
goto :fim

:sem_git
echo.
echo Nao encontrei o Git. Instale em https://git-scm.com/download/win e abra este arquivo de novo.
echo [%date% %time%] git nao encontrado >> "%LOG%"
set "CODIGO=9"
goto :fim

:falha_envio
echo.
echo O envio foi recusado. Se o GitHub ja tem arquivos que esta pasta nao tem, rode "git pull --rebase origin main" aqui e abra este arquivo de novo.
echo Se pediu login e falhou, entre na sua conta quando o Windows abrir a janela de acesso do GitHub.
set "CODIGO=2"
goto :fim

:falha
echo.
echo Algo deu errado antes do envio. Veja o arquivo logs\atualizacao.log.
set "CODIGO=1"
goto :fim

:fim
echo [%date% %time%] atualizacao terminou com codigo %CODIGO% >> "%LOG%"
echo.
pause
exit /b %CODIGO%
