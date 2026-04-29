# Railway Deployment Guide for TruckHub Backend

## Шаг 1: Установка Railway CLI

```powershell
npm install -g @railway/cli
```

## Шаг 2: Вход в аккаунт

```powershell
railway login
```

Откроется браузер — авторизуйся.

## Шаг 3: Инициализация проекта

```powershell
cd C:\Users\MANAGER1\.verdent\verdent-projects\TruckHub\backend
railway init
```

Выбери:
- **Create New Project**
- Название: `truckhub-api`

## Шаг 4: Добавление базы данных

```powershell
railway add --database postgres
```

## Шаг 5: Установка переменных окружения

```powershell
railway variables set ENV=production
railway variables set SECRET_KEY=$(openssl rand -hex 32)
railway variables set CORS_ORIGINS=https://truckhub-frontend-rfj0vzqox-bigtrakm7-6887s-projects.vercel.app
```

## Шаг 6: Деплой

```powershell
railway up
```

## Шаг 7: Получение URL

```powershell
railway domain
```

Копируй URL (например: `https://truckhub-api.up.railway.app`)

## Шаг 8: Обновление Frontend

1. Иди в настройки Vercel проекта
2. Добавь переменную окружения:
   - Name: `VITE_API_BASE_URL`
   - Value: `https://truckhub-api.up.railway.app`
3. Перезапусти деплой

## Готово!

Сайт полностью работает в интернете!
