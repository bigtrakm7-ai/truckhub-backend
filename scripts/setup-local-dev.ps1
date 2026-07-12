# TruckGrad — первичная настройка локальной разработки (Windows)
# Запуск: powershell -ExecutionPolicy Bypass -File scripts\setup-local-dev.ps1

$Backend = "C:\Users\MANAGER1\.verdent\verdent-projects\TruckHub\backend"
$Frontend = "C:\Users\MANAGER1\.verdent\verdent-projects\TruckHub\frontend"

Write-Host "=== TruckGrad: настройка локальной разработки ===" -ForegroundColor Cyan

if (-not (Test-Path $Backend)) {
    Write-Host "Backend не найден: $Backend" -ForegroundColor Red
    exit 1
}

Set-Location $Backend
Write-Host "`n[1/4] Backend: git pull..." -ForegroundColor Yellow
git pull origin master

Write-Host "[2/4] Backend: pip install..." -ForegroundColor Yellow
python -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Создан .env из .env.example" -ForegroundColor Green
}

if (Test-Path $Frontend) {
    Set-Location $Frontend
    Write-Host "`n[3/4] Frontend: npm install..." -ForegroundColor Yellow
    npm install

    $envLocal = Join-Path $Frontend ".env.local"
    $envExample = Join-Path $Backend "scripts\frontend.env.local.example"
    if (-not (Test-Path $envLocal) -and (Test-Path $envExample)) {
        Copy-Item $envExample $envLocal
        Write-Host "Создан frontend/.env.local" -ForegroundColor Green
    }
} else {
    Write-Host "Frontend не найден: $Frontend" -ForegroundColor Yellow
}

Set-Location $Backend
Write-Host "`n[4/4] Готово!" -ForegroundColor Green
Write-Host @"

Запуск:
  .\scripts\start-truckgrad-dev.bat

Или вручную:
  API:  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
  UI:   cd frontend && npm run dev -- --host 127.0.0.1 --port 3023

Сайт: http://127.0.0.1:3023
API:  http://127.0.0.1:8000/docs

"@ -ForegroundColor Cyan
