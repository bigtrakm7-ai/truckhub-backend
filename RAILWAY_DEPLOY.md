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
