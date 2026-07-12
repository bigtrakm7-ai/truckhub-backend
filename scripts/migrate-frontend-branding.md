# Миграция frontend: TruckHub → TruckGrad

Выполните в папке `frontend` на вашем ПК.

## 1. Переменные окружения

`.env` и `.env.production`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_APP_NAME=TruckGrad
VITE_SITE_URL=https://truckgrad.ru
```

На Vercel (Production):

```env
VITE_API_BASE_URL=https://truckhub-api.onrender.com
```

(или новый URL после переименования сервиса на Render)

## 2. public/manifest.json

```json
"name": "TruckGrad - Запчасти для грузовиков",
"short_name": "TruckGrad",
```

## 3. Поиск и замена в src/

| Было | Стало |
|------|-------|
| `truckhub_access_token` | `truckgrad_access_token` |
| `truckhub_active_mode` | `truckgrad_active_mode` |
| `truckhub_compare` | `truckgrad_compare` |
| `truckhub_favorites` | `truckgrad_favorites` |
| `truckhub_favorites_v2` | `truckgrad_favorites_v2` |
| `truckhub:` (события) | `truckgrad:` |
| `TruckHub` | `TruckGrad` |
| `truckhub-api.onrender.com` | из `import.meta.env.VITE_API_BASE_URL` |

## 4. Миграция localStorage (один раз при старте)

```typescript
const MIGRATIONS: [string, string][] = [
  ['truckhub_access_token', 'truckgrad_access_token'],
  ['truckhub_active_mode', 'truckgrad_active_mode'],
  ['truckhub_compare', 'truckgrad_compare'],
  ['truckhub_favorites_v2', 'truckgrad_favorites_v2'],
  ['truckhub_favorites', 'truckgrad_favorites'],
];
for (const [oldKey, newKey] of MIGRATIONS) {
  const v = localStorage.getItem(oldKey);
  if (v !== null && localStorage.getItem(newKey) === null) {
    localStorage.setItem(newKey, v);
    localStorage.removeItem(oldKey);
  }
}
```

## 5. Деплой

```bash
npm run build
# Vercel: redeploy с обновлёнными env
```

## 6. GitHub (рекомендуется)

```bash
git init
git remote add origin https://github.com/bigtrakm7-ai/truckgrad-frontend.git
git add .
git commit -m "TruckGrad frontend"
git push -u origin main
```
