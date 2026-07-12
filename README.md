# TruckGrad Backend

Маркетплейс запчастей для грузовиков — **https://truckgrad.ru**

## Локальная разработка (рекомендуется, без Render)

**Полная инструкция:** [LOCAL_DEV.md](LOCAL_DEV.md)

```powershell
# Один раз
powershell -ExecutionPolicy Bypass -File scripts\setup-local-dev.ps1

# Каждый запуск
scripts\start-truckgrad-dev.bat
```

| Сайт dev | http://127.0.0.1:3023 |
| API / Swagger | http://127.0.0.1:8000/docs |

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Frontend

Скопируйте `scripts/frontend.env.local.example` → `frontend/.env.local`  
Подробнее: `scripts/migrate-frontend-branding.md`

## Продакшен (опционально, Render сейчас выключен)

См. `RAILWAY_DEPLOY.md` — когда понадобится живой API для truckgrad.ru.
