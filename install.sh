#!/bin/bash
set -e
echo "=== Установка Сервисного центра 'Мастер' ==="

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Установите Python 3.10+"
    exit 1
fi

# Создание виртуального окружения
echo "📦 Создание виртуального окружения..."
python3 -m venv venv
source venv/bin/activate

# Обновление pip
pip install --upgrade pip

# Установка зависимостей
echo "📚 Установка зависимостей..."
pip install -r requirements.txt

# Создание .env из примера
if [ ! -f .env ]; then
    cp .env.example .env 2>/dev/null || echo "SECRET_KEY=change-this-key" > .env
    echo "🔐 Создан файл .env. Отредактируйте его при необходимости."
fi

# Инициализация базы данных
echo "🗄️ Инициализация базы данных..."
python init_db.py

# Создание папки для бэкапов
mkdir -p backups

echo "✅ Установка завершена!"
echo "🚀 Запустите сервер: source venv/bin/activate && python app.py"
echo "🔑 Логин: admin, пароль: admin123"