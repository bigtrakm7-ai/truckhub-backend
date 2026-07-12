# TruckGrad Backend

Маркетплейс запчастей для грузовиков — **https://truckgrad.ru**

## Быстрый старт (локально)

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- API: http://127.0.0.1:8000  
- Swagger: http://127.0.0.1:8000/docs  

## Render (продакшен)

### Если сервис приостановлен (Suspended by you)

**Вариант A — один клик в браузере**

1. https://dashboard.render.com → **truckhub-api**
2. Кнопка **Resume** (вверху справа)

**Вариант B — через API**

```bash
export RENDER_API_KEY=rnd_ваш_ключ
export RENDER_SERVICE_ID=srv_ваш_id
python3 scripts/render_resume.py
```

Ключ API: https://dashboard.render.com/u/settings#api-keys

### Новый деплой (если Resume недоступен)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/bigtrakm7-ai/truckhub-backend)

После деплоя обновите `VITE_API_BASE_URL` на Vercel.

## Frontend

Инструкция: `scripts/migrate-frontend-branding.md`  
Запуск dev (Windows): `scripts/start-truckgrad-dev.bat`
