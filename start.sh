#!/bin/bash

# --- Конфигурация ---
VENV_ACTIVATE=".venv/bin/activate"
APP_PORT=5000
APP_URL="http://127.0.0.1:$APP_PORT"

# --- Шаг 1: Активация окружения ---
if [ -f "$VENV_ACTIVATE" ]; then
    source "$VENV_ACTIVATE"
else
    echo "❌ Ошибка: Виртуальное окружение не найдено."
    exit 1
fi

# --- Шаг 2: Освобождение порта ---
echo "🔎 Проверяю порт $APP_PORT..."
for pid in $(lsof -t -i:$APP_PORT); do
    if [ -n "$pid" ]; then
        echo "⚠️  Порт занят (PID: $pid). Останавливаю..."
        kill -9 "$pid"
    fi
done
sleep 0.5 

# --- Шаг 3: Автоматическое открытие браузера ---
echo "🚀 Открываю дашборд в браузере..."
# (Здесь ваша проверенная логика для поиска браузера)
BROWSER_CMD=""
if command -v yandex-browser-stable &> /dev/null; then BROWSER_CMD="yandex-browser-stable";
elif command -v yandex-browser &> /dev/null; then BROWSER_CMD="yandex-browser"; fi

if [ -n "$BROWSER_CMD" ]; then
    "$BROWSER_CMD" "$APP_URL" &
else 
    if command -v xdg-open &> /dev/null; then
        xdg-open "$APP_URL" &
    else
         echo "⚠️ Не удалось найти браузер. Откройте вручную: $APP_URL"
    fi
fi

# --- Шаг 4: Запуск ВСЕЙ системы через Foreman ---
echo "Запускаю веб-сервер и Telegram-бота..."
echo "Нажмите Ctrl+C в этом окне, чтобы остановить ВСЁ."
foreman start