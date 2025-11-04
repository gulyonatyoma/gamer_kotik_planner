# bot.py
import logging
import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from sqlalchemy import func

# --- 1. ИМПОРТ ИЗ НАШЕГО ФАЙЛА DATABASE.PY ---
from database import SessionLocal, Project, Task

# --- 2. КОНФИГУРАЦИЯ БОТА ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- 3. НОВИНКА: Определяем состояния для нашего диалога ---
# Это как "шаги" в нашем разговоре с пользователем
GET_TITLE, CHOOSE_PROJECT = range(2)


# --- 4. ОБЫЧНЫЕ КОМАНДЫ (почти без изменений) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(f"Привет, {user.first_name}! Ассистент готов к работе.\n\n"
                                    "<b>Новые команды:</b>\n"
                                    "/newtask - создать задачу в диалоге\n"
                                    "/deletetask - удалить задачу")

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = SessionLocal()
    try:
        tasks = session.query(Task).filter_by(status='pending', is_today=True).order_by(Task.created_at).all()
        if not tasks:
            await update.message.reply_text("🎯 План на сегодня пуст!")
            return
        message = "<b>🎯 План на сегодня:</b>\n\n" + "\n".join([f"• {task.title}" for task in tasks])
        await update.message.reply_html(message)
    finally:
        session.close()

async def projects_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = SessionLocal()
    try:
        projects = session.query(Project).order_by(Project.name).all()
        if not projects:
            await update.message.reply_text("📂 У вас пока нет проектов.")
            return
        message = "<b>📂 Ваши проекты:</b>\n\n" + "\n".join([f"• {proj.name}" for proj in projects])
        await update.message.reply_html(message)
    finally:
        session.close()


# --- 5. НОВЫЙ ДИАЛОГ ДЛЯ СОЗДАНИЯ ЗАДАЧИ ---

# Шаг 1: Пользователь отправляет /newtask
async def new_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отлично! Введите название новой задачи. (Для отмены введите /cancel)")
    return GET_TITLE # Переходим на следующий шаг - ожидание названия

# Шаг 2: Пользователь вводит название, бот предлагает проекты
async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    task_title = update.message.text
    context.user_data['task_title'] = task_title # Временно сохраняем название
    
    session = SessionLocal()
    try:
        projects = session.query(Project).order_by(Project.name).all()
    finally:
        session.close()

    keyboard = [
        # Первая кнопка - всегда добавить в "План на сегодня" (без проекта)
        [InlineKeyboardButton("🎯 В План на сегодня", callback_data='select_project:today')],
    ]
    # Добавляем кнопки для каждого проекта
    for proj in projects:
        keyboard.append([InlineKeyboardButton(f"📂 {proj.name}", callback_data=f'select_project:{proj.id}')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Задача: '{task_title}'\n\nКуда ее добавить?", reply_markup=reply_markup)
    
    return CHOOSE_PROJECT # Переходим на шаг ожидания нажатия кнопки

# Шаг 3 (обработчик кнопок): Пользователь нажимает кнопку, задача создается
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer() # Обязательно "отвечаем" на нажатие

    # Разбираем данные с кнопки, например "select_project:123"
    action, value = query.data.split(':')
    
    task_title = context.user_data.get('task_title')
    if not task_title:
        await query.edit_message_text(text="Произошла ошибка, попробуйте снова /newtask")
        return ConversationHandler.END

    session = SessionLocal()
    try:
        if value == 'today': # Если нажали "В План на сегодня"
            new_task = Task(title=task_title, project_id=None, is_today=True)
            session.add(new_task)
            session.commit()
            await query.edit_message_text(text=f"✅ Задача '{task_title}' добавлена в 'План на сегодня'.")
        else: # Если выбрали конкретный проект
            project_id = int(value)
            project = session.query(Project).get(project_id)
            if project:
                new_task = Task(title=task_title, project_id=project.id, is_today=False)
                session.add(new_task)
                session.commit()
                await query.edit_message_text(text=f"✅ Задача '{task_title}' добавлена в проект '{project.name}'.")
            else:
                await query.edit_message_text(text="Ошибка: проект не найден.")
    finally:
        session.close()

    context.user_data.clear() # Очищаем временные данные
    return ConversationHandler.END # Завершаем диалог

# Шаг 4 (отмена): Пользователь вводит /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Действие отменено.")
    return ConversationHandler.END


# --- 6. НОВАЯ ФУНКЦИЯ ИНТЕРАКТИВНОГО УДАЛЕНИЯ ---

# Пользователь отправляет /deletetask
async def delete_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = SessionLocal()
    try:
        # Собираем задачи из "Плана на сегодня" и "Входящих"
        tasks_today = session.query(Task).filter_by(status='pending', is_today=True).all()
        tasks_inbox = session.query(Task).filter_by(status='pending', is_today=False, project_id=None).all()
        
        all_tasks = tasks_today + tasks_inbox
        
        if not all_tasks:
            await update.message.reply_text("Нет задач для удаления в 'Плане на сегодня' или 'Входящих'.")
            return

        keyboard = []
        for task in all_tasks:
            # Для каждой задачи создаем кнопку с callback_data вида "delete_task:123"
            button = InlineKeyboardButton(f"🗑️ {task.title}", callback_data=f'delete_task:{task.id}')
            keyboard.append([button])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Какую задачу вы хотите удалить?", reply_markup=reply_markup)
    finally:
        session.close()

# Пользователь нажимает на кнопку "Удалить"
async def delete_task_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    action, task_id_str = query.data.split(':')
    task_id = int(task_id_str)
    
    session = SessionLocal()
    try:
        task = session.query(Task).get(task_id)
        if task:
            task_title = task.title
            session.delete(task)
            session.commit()
            await query.edit_message_text(text=f"✅ Задача '{task_title}' удалена.")
        else:
            await query.edit_message_text(text="Задача уже была удалена.")
    finally:
        session.close()


# --- 7. ГЛАВНАЯ ФУНКЦИЯ С НОВЫМИ ОБРАБОТЧИКАМИ ---
def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    # Создаем ConversationHandler для диалога добавления задачи
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("newtask", new_task_start)],
        states={
            GET_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            CHOOSE_PROJECT: [CallbackQueryHandler(button_handler, pattern='^select_project:.*')],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    # Добавляем обычные команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("projects", projects_command))
    
    # Добавляем обработчики для удаления
    application.add_handler(CommandHandler("deletetask", delete_task_start))
    application.add_handler(CallbackQueryHandler(delete_task_confirm, pattern='^delete_task:.*'))

    print("Бот запущен и готов к работе в интерактивном режиме...")
    application.run_polling()

if __name__ == "__main__":
    main()