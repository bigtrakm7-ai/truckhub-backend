@echo off
REM TruckGrad — запуск backend + frontend для разработки (Windows)
REM Пути из вашей схемы проекта

set BACKEND=C:\Users\MANAGER1\.verdent\verdent-projects\TruckHub\backend
set FRONTEND=C:\Users\MANAGER1\.verdent\verdent-projects\TruckHub\frontend

echo Запуск TruckGrad Backend на http://127.0.0.1:8000
start "TruckGrad API" cmd /k "cd /d %BACKEND% && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

timeout /t 3 /nobreak >nul

echo Запуск TruckGrad Frontend на http://127.0.0.1:3023
start "TruckGrad UI" cmd /k "cd /d %FRONTEND% && npm run dev -- --host 127.0.0.1 --port 3023"

echo.
echo Готово:
echo   Сайт:  http://127.0.0.1:3023
echo   API:   http://127.0.0.1:8000/docs
pause
