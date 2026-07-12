# Локальная разработка TruckGrad (без Render)

Сайт: https://truckgrad.ru — для **разработки** используйте только локальный backend + frontend.

## Структура на ПК

```
C:\Users\MANAGER1\.verdent\verdent-projects\TruckHub\
├── backend\    ← этот репозиторий (GitHub: truckhub-backend)
└── frontend\   ← UI (Vite/React)
```

## Шаг 1 — один раз: настройка backend

```powershell
cd C:\Users\MANAGER1\.verdent\verdent-projects\TruckHub\backend
git pull origin master
pip install -r requirements.txt
copy .env.example .env
```

Файл `.env` уже готов для локальной работы (SQLite, mock-интеграции).

## Шаг 2 — один раз: настройка frontend

```powershell
cd C:\Users\MANAGER1\.verdent\verdent-projects\TruckHub\frontend
npm install
```

Создайте или отредактируйте `.env.local`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_APP_NAME=TruckGrad
```

> **Важно:** не используйте `truckhub-api.onrender.com` — Render сейчас выключен.

## Шаг 3 — каждый день: запуск

**Способ 1 — один клик (bat):**

```powershell
cd C:\Users\MANAGER1\.verdent\verdent-projects\TruckHub\backend
.\scripts\start-truckgrad-dev.bat
```

**Способ 2 — два терминала:**

```powershell
# Терминал 1 — API
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Терминал 2 — сайт
cd frontend
npm run dev -- --host 127.0.0.1 --port 3023
```

## Адреса

| Что | URL |
|-----|-----|
| **Сайт (dev)** | http://127.0.0.1:3023 |
| **API** | http://127.0.0.1:8000 |
| **Swagger** | http://127.0.0.1:8000/docs |
| **Health** | http://127.0.0.1:8000/health |

## Тестовые аккаунты (из seed)

| Роль | Email | Пароль |
|------|-------|--------|
| Поставщик | bigtrakm7@gmail.com | Test12345! |
| Админ | u1225325713@example.com | Pass12345! |

## Что работает без Render

- Каталог, корзина, заказы (SQLite локально)
- Авторизация JWT
- Mock: доставка, VIN, email, SMS
- Админка `/admin`

## Что не нужно для dev

- Render / PostgreSQL
- Redis / Elasticsearch (опционально, без них API стартует)
- Оплата на Render

## Обновление кода

```powershell
cd backend
git pull origin master
pip install -r requirements.txt
```

### Ошибка «Your local changes would be overwritten»

```powershell
cd C:\Users\MANAGER1\.verdent\verdent-projects\TruckHub\backend
git stash push -m "backup"
git pull origin master
powershell -ExecutionPolicy Bypass -File scripts\setup-local-dev.ps1
.\scripts\start-truckgrad-dev.bat
```

Или одной командой: `scripts\fix-git-pull.bat`

Если локальные правки **не нужны** (взять всё с GitHub):

```powershell
git reset --hard origin/master
git pull origin master
```

## Frontend → TruckGrad

См. `scripts/migrate-frontend-branding.md`

## Когда понадобится прод

Только когда захотите, чтобы **truckgrad.ru** снова ходил в живой API — тогда Render/Railway + карта оплаты. Для разработки это не нужно.
