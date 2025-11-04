#!/bin/bash

# Определяем директорию, в которой находится наш скрипт
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
ENV_FILE="${SCRIPT_DIR}/.env"

# Проверяем, существует ли файл .env
if [ ! -f "$ENV_FILE" ]; then
    echo "Ошибка: Файл .env не найден в директории скрипта: $ENV_FILE" >&2
    exit 1
fi

# Загружаем переменные из .env
source "$ENV_FILE"

# Проверяем, задана ли переменная ONEFILELLM_PATH
if [ -z "$ONEFILELLM_PATH" ]; then
    echo "Ошибка: Переменная ONEFILELLM_PATH не задана в файле $ENV_FILE" >&2
    exit 1
fi

# --- ИСПРАВЛЕННАЯ КОМАНДА FIND ---
# Теперь мы исключаем папки .venv, .git и __pycache__ целиком, а не только их содержимое.
# Мы также исключаем директории из вывода, оставляя только файлы.
SOURCE_FILES=$(find . -type f \
    -not -path "./.git/*" \
    -not -path "./.venv/*" \
    -not -path "./__pycache__/*" \
    -not -name "package_project.sh" \
    -not -name "package_project_debug.sh" \
    -not -name "*.txt" \
    -not -name ".env" \
    -not -name "output.xml")

echo "Найдены следующие файлы для упаковки:"
echo "$SOURCE_FILES"
echo "-------------------------------------"

# Проверяем, что список файлов не пустой
if [ -z "$SOURCE_FILES" ]; then
    echo "Ошибка: Не найдено ни одного файла для упаковки. Проверьте правила исключения в скрипте." >&2
    exit 1
fi


# Активируем виртуальное окружение onefilellm
source "${ONEFILELLM_PATH}/.venv/bin/activate"

# Запускаем onefilellm.py с найденными файлами
python "${ONEFILELLM_PATH}/onefilellm.py" ${SOURCE_FILES}

# Удаляем временный файл, если он создается
rm -f output.xml