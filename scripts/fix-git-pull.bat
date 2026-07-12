@echo off
REM Восстановление после ошибки git pull — запуск из папки backend
cd /d "%~dp0.."

echo === TruckGrad: обновление с GitHub ===

git status --short
echo.

git stash push -m "truckgrad-backup-before-pull"
if errorlevel 1 (
    echo stash пропущен или пусто
)

git pull origin master
if errorlevel 1 (
    echo.
    echo ОШИБКА git pull. Попробуйте:
    echo   git reset --hard origin/master
    echo если локальные правки не нужны.
    pause
    exit /b 1
)

echo.
echo OK. Теперь:
echo   powershell -ExecutionPolicy Bypass -File scripts\setup-local-dev.ps1
echo   scripts\start-truckgrad-dev.bat
pause
