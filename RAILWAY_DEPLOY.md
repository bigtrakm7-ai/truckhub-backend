# Railway Deployment Guide for TruckGrad Backend

Сайт проекта: **https://truckgrad.ru**

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
