@echo off
set "SCRIPT_DIR=%~dp0"
echo A configurar Bot Lite Energia...

:: Verificar se o eXLib.mix ja esta na pasta
if exist "%SCRIPT_DIR%eXLib.mix" (
    echo [OK] eXLib.mix encontrado.
) else (
    echo [ERRO] eXLib.mix NAO encontrado na pasta!
    echo Copia o eXLib.mix para esta pasta antes de continuar.
    pause
    exit
)

:: Copiar ficheiros para a pasta do jogo (mesma pasta onde esta o init.py)
echo A copiar ficheiros do bot...
xcopy /E /Y /Q "%SCRIPT_DIR%MT2Robs" "%SCRIPT_DIR%MT2Robs" >nul 2>&1
xcopy /Y /Q "%SCRIPT_DIR%init.py" "%SCRIPT_DIR%init.py" >nul 2>&1

:: Apagar pycache para forcar recompilacao
if exist "%SCRIPT_DIR%MT2Robs\Modules\__pycache__" (
    rmdir /S /Q "%SCRIPT_DIR%MT2Robs\Modules\__pycache__"
    echo [OK] __pycache__ apagado
)

:: Esconder ficheiros e pastas
echo Escondendo ficheiros...
attrib +h "%SCRIPT_DIR%MT2Robs" /s /d 2>nul
attrib +h "%SCRIPT_DIR%eXLib.mix" 2>nul

echo.
echo Configuracao concluida!
echo Ficheiros atualizados e ocultados.
pause
