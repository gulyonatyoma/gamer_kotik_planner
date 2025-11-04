#!/bin/bash

# ==============================================================================
# УСТАНОВОЧНЫЙ СКРИПТ ДЛЯ СИСТЕМЫ ПРОДУКТИВНОСТИ
# Этот скрипт настроит веб-приложение и Telegram-бота как системные службы.
# ==============================================================================

# --- Конфигурация ---
# Абсолютный путь к директории проекта. Скрипт определит его автоматически.
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Имя вашего пользователя. Скрипт также определит его автоматически.
APP_USER=$(whoami)

echo "--- НАЧАЛО УСТАНОВКИ ---"
echo "Пользователь: $APP_USER"
echo "Директория проекта: $PROJECT_DIR"
echo "--------------------------"

# --- Шаг 1: Установка зависимостей (Nginx, Ruby, Foreman) ---
echo "⚙️  Шаг 1: Установка системных зависимостей (Nginx, Ruby)..."
sudo dnf install -y nginx ruby || { echo "❌ Ошибка установки зависимостей. Прервано."; exit 1; }
sudo gem install foreman || { echo "❌ Ошибка установки Foreman. Прервано."; exit 1; }
echo "✅ Зависимости установлены."
echo ""

# --- Шаг 2: Создание файла wsgi.py ---
echo "⚙️  Шаг 2: Создание файла wsgi.py..."
cat > "$PROJECT_DIR/wsgi.py" <<EOL
# wsgi.py
from app import app

if __name__ == "__main__":
    app.run()
EOL
echo "✅ Файл wsgi.py создан."
echo ""

# --- Шаг 3: Создание файлов служб systemd ---
echo "⚙️  Шаг 3: Создание служб systemd (planner-web и planner-bot)..."

# Создаем planner-web.service
sudo bash -c "cat > /etc/systemd/system/planner-web.service" <<EOL
[Unit]
Description=Gunicorn instance for Planner Web App
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/.venv/bin"
ExecStart=$PROJECT_DIR/.venv/bin/gunicorn --workers 3 --bind unix:planner.sock -m 007 wsgi:app

[Install]
WantedBy=multi-user.target
EOL

# Создаем planner-bot.service
sudo bash -c "cat > /etc/systemd/system/planner-bot.service" <<EOL
[Unit]
Description=Telegram Bot for Planner App
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/.venv/bin/python3 bot.py

[Install]
WantedBy=multi-user.target
EOL

echo "✅ Файлы служб созданы."
echo ""

# --- Шаг 4: Настройка Nginx ---
echo "⚙️  Шаг 4: Настройка Nginx..."
sudo bash -c "cat > /etc/nginx/conf.d/planner.conf" <<EOL
server {
    listen 80;
    server_name localhost 127.0.0.1;

    location / {
        proxy_pass http://unix:$PROJECT_DIR/planner.sock;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOL
echo "✅ Конфигурация Nginx создана."
echo ""

# --- Шаг 5: Настройка Firewall и SELinux ---
echo "⚙️  Шаг 5: Настройка Firewall и SELinux..."
sudo firewall-cmd --permanent --add-service=http --quiet
sudo firewall-cmd --reload --quiet
sudo setsebool -P httpd_can_network_connect 1
echo "✅ Firewall и SELinux настроены."
echo ""

# --- Шаг 6: Запуск всех служб ---
echo "⚙️  Шаг 6: Запуск и включение автозапуска служб..."
sudo systemctl daemon-reload
sudo systemctl start planner-web.service
sudo systemctl start planner-bot.service
sudo systemctl start nginx

sudo systemctl enable planner-web.service
sudo systemctl enable planner-bot.service
sudo systemctl enable nginx
echo "✅ Все службы запущены и добавлены в автозапуск."
echo ""

# --- Финальная проверка ---
echo "--- ПРОВЕРКА СТАТУСА ---"
sleep 2 # Даем службам время на запуск
sudo systemctl is-active --quiet planner-web && echo "🟢 Веб-сервер активен" || echo "🔴 Ошибка веб-сервера"
sudo systemctl is-active --quiet planner-bot && echo "🟢 Telegram-бот активен" || echo "🔴 Ошибка Telegram-бота"
sudo systemctl is-active --quiet nginx && echo "🟢 Nginx активен" || echo "🔴 Ошибка Nginx"
echo "-------------------------"
echo ""
echo "🎉 Установка завершена! Ваша система продуктивности развернута."
echo "Откройте в браузере: http://localhost"