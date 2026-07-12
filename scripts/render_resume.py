#!/usr/bin/env python3
"""Возобновить приостановленный сервис на Render через API.

1. Render Dashboard → Account Settings → API Keys → Create
2. Скопируйте Service ID: откройте truckhub-api → URL содержит srv-xxxxx
   или в Settings → внизу страницы

Использование:
  export RENDER_API_KEY=rnd_...
  export RENDER_SERVICE_ID=srv_...
  python3 scripts/render_resume.py
"""

import os
import sys

import httpx


def main() -> int:
    api_key = os.environ.get("RENDER_API_KEY", "").strip()
    service_id = os.environ.get("RENDER_SERVICE_ID", "").strip()

    if not api_key or not service_id:
        print("Задайте переменные RENDER_API_KEY и RENDER_SERVICE_ID", file=sys.stderr)
        print("API Key: https://dashboard.render.com/u/settings#api-keys", file=sys.stderr)
        return 1

    url = f"https://api.render.com/v1/services/{service_id}/resume"
    resp = httpx.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        timeout=30.0,
    )

    print(f"HTTP {resp.status_code}")
    print(resp.text)

    if resp.status_code in (200, 202):
        print("\nСервис возобновляется. Проверьте через 2-5 мин:")
        print("https://truckhub-api.onrender.com/health")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
