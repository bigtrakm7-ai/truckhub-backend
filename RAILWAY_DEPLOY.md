# Railway Deployment Guide for TruckGrad Backend

Сайт проекта: **https://truckgrad.ru**

## Переименование репозитория на GitHub

Текущее имя: `truckhub-backend` → рекомендуемое: **`truckgrad-backend`**

1. Откройте https://github.com/bigtrakm7-ai/truckhub-backend/settings
2. В разделе **Repository name** введите `truckgrad-backend` и нажмите **Rename**
3. Локально обновите remote:
   ```bash
   git remote set-url origin https://github.com/bigtrakm7-ai/truckgrad-backend.git
   ```
4. Обновите описание репозитория: *TruckGrad API — backend маркетплейса запчастей*

> Переименование делает владелец репозитория. У Cloud Agent нет прав на rename через API.

## Брендинг Frontend (truckgrad.ru)

Репозиторий frontend **не подключён** к этому workspace. На проде (`truckgrad.ru`) ещё остались следы TruckHub:

| Где | Сейчас | Нужно |
|-----|--------|-------|
| `public/manifest.json` | `TruckHub` | `TruckGrad` |
| `VITE_API_BASE_URL` | `https://truckhub-api.onrender.com` | URL вашего TruckGrad API |
| localStorage-ключи | `truckhub_access_token`, `truckhub_favorites_*` | `truckgrad_*` (с миграцией старых ключей) |
| Custom events | `truckhub:favorites-changed` | `truckgrad:favorites-changed` |

После правок в frontend-репозитории: пересоберите и задеплойте на домен `truckgrad.ru`.

**Не путать:** `truckhub.vercel.app` — отдельный проект (грузоперевозки), к TruckGrad не относится.

## Шаг 1: Установка Railway CLI

```powershell
npm install -g @railway/cli
```

## Шаг 2: Вход в аккаунт

```powershell
railway login
```

Откроется браузер — авторизуйтесь.

## Шаг 3: Инициализация проекта

```powershell
cd путь\к\репозиторию-backend
railway init
```

Выберите:
- **Create New Project**
- Название: `truckgrad-api`

## Шаг 4: Добавление базы данных

```powershell
railway add --database postgres
```

## Шаг 5: Установка переменных окружения

```powershell
railway variables set ENV=production
railway variables set SECRET_KEY=$(openssl rand -hex 32)
railway variables set CORS_ORIGINS=https://truckgrad.ru,https://www.truckgrad.ru
```

## Шаг 6: Деплой

```powershell
railway up
```

## Шаг 7: Получение URL

```powershell
railway domain
```

Скопируйте URL (например: `https://truckgrad-api.up.railway.app`)

## Шаг 8: Обновление Frontend

1. Откройте настройки Vercel-проекта TruckGrad
2. Добавьте переменную окружения:
   - Name: `VITE_API_BASE_URL`
   - Value: `https://truckgrad-api.up.railway.app`
3. Перезапустите деплой

## Готово!

TruckGrad полностью работает в интернете.

---

## Деплой на Render (truckgrad.ru)

### Если сервис `truckhub-api` приостановлен

1. Откройте https://dashboard.render.com
2. Найдите сервис **truckhub-api** (или Web Service с этим URL)
3. Нажмите **Resume service** / **Restore** (на бесплатном плане сервис «засыпает» и может быть отключён)
4. Если восстановить нельзя — **New + Web Service** → подключите репозиторий `truckgrad-backend`

### Настройки Web Service

| Поле | Значение |
|------|----------|
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **Python Version** | 3.11+ |

### Переменные окружения (Environment)

| Key | Value |
|-----|-------|
| `ENV` | `production` |
| `SECRET_KEY` | случайная строка (32+ символа) |
| `DATABASE_URL` | из Render PostgreSQL (Internal Database URL) |
| `CORS_ORIGINS` | `https://truckgrad.ru,https://www.truckgrad.ru,https://truckhub-frontend-phi.vercel.app` |
| `PROVIDER_MODE` | `mock` (пока без реальных ключей интеграций) |

### PostgreSQL на Render

1. **New + PostgreSQL** → имя `truckgrad-db`
2. Скопируйте **Internal Database URL** в `DATABASE_URL` web-сервиса
3. В `requirements.txt` должен быть пакет `asyncpg` (для async PostgreSQL)

### После деплоя

1. Проверьте: `https://ВАШ-СЕРВИС.onrender.com/health` → `"status": "работает"`
2. В **Vercel** (frontend) обновите:
   - `VITE_API_BASE_URL` = URL вашего Render API
3. **Redeploy** frontend на Vercel

### Переименование на Render (по желанию)

Settings → Name → `truckgrad-api` (URL `.onrender.com` может остаться старым, пока не создадите новый сервис)
