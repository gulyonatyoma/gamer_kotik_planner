# bot.py
import logging
import os
from datetime import datetime
import re

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

# --- 1. НАСТРОЙКА ПОДКЛЮЧЕНИЯ К БАЗЕ ДАННЫХ ---
app = Flask(__name__)
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'Yfnfif1999!')
DB_URI = f"postgresql://planner_user:{DB_PASSWORD}@localhost:5432/planner_db"
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- 2. МОДЕЛИ (Идентичны app.py) ---
class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    tasks = db.relationship('Task', backref='project', lazy=True, cascade="all, delete-orphan")

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='pending')
    is_today = db.Column(db.Boolean, default=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

# --- 3. КОНФИГУРАЦИЯ БОТА ---
BOT_TOKEN = "8596801086:AAEBJTSqz_ivunraaThugqtta7DP_0410wU"
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- 4. РЕАЛИЗАЦИЯ КОМАНД ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(f"Привет, {user.first_name}! Ассистент готов к работе.")

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with app.app_context():
        tasks = Task.query.filter_by(status='pending', is_today=True).order_by(Task.created_at).all()
    if not tasks: await update.message.reply_text("🎯 План на сегодня пуст!"); return
    message = "<b>🎯 План на сегодня:</b>\n\n" + "\n".join([f"• {task.title}" for task in tasks])
    await update.message.reply_html(message)

async def inbox_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with app.app_context():
        tasks = Task.query.filter_by(status='pending', is_today=False, project_id=None).order_by(Task.created_at).all()
    if not tasks: await update.message.reply_text("📥 \"Входящие\" пусты."); return
    message = "<b>📥 Задачи во 'Входящих':</b>\n\n" + "\n".join([f"• {task.title}" for task in tasks])
    await update.message.reply_html(message)

async def projects_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with app.app_context():
        projects = Project.query.order_by(Project.name).all()
    if not projects: await update.message.reply_text("📂 У вас пока нет проектов."); return
    message = "<b>📂 Ваши проекты:</b>\n\n" + "\n".join([f"• {proj.name}" for proj in projects])
    await update.message.reply_html(message)

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    task_text = ' '.join(context.args)
    if not task_text:
        await update.message.reply_text("Использование: /add [текст задачи] #проект (необязательно)")
        return

    project_name = None
    match = re.search(r'#(\S+)', task_text)
    if match:
        project_name = match.group(1)
        task_title = re.sub(r'\s*#\S+\s*', '', task_text).strip()
    else:
        task_title = task_text.strip()
    
    with app.app_context():
        project_id = None
        if project_name:
            project = Project.query.filter(func.lower(Project.name) == func.lower(project_name)).first()
            if project: project_id = project.id
        
        # --- ИЗМЕНЕНИЕ: Задачи без проекта теперь попадают в "План на сегодня" ---
        new_task = Task(title=task_title, project_id=project_id, is_today=(not project_id))
        db.session.add(new_task)
        db.session.commit()
        
    response = f"✅ Задача '{task_title}' добавлена"
    if project_name: response += f" в проект '{project_name}'."
    else: response += " в 'План на сегодня'."
    await update.message.reply_text(response)

### НОВЫЕ КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ ПРОЕКТАМИ ###
async def add_project_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    project_name = ' '.join(context.args)
    if not project_name:
        await update.message.reply_text("Использование: /add_project [название проекта]")
        return
    
    with app.app_context():
        existing = Project.query.filter(func.lower(Project.name) == func.lower(project_name)).first()
        if existing:
            await update.message.reply_text(f"❗️ Проект '{project_name}' уже существует.")
            return
        
        new_project = Project(name=project_name)
        db.session.add(new_project)
        db.session.add(Task(title="Начать работу над проектом", project=new_project))
        db.session.commit()
    
    await update.message.reply_text(f"✅ Проект '{project_name}' успешно создан.")

async def delete_project_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    project_name = ' '.join(context.args)
    if not project_name:
        await update.message.reply_text("Использование: /delete_project [точное название проекта]")
        return
        
    with app.app_context():
        project = Project.query.filter(func.lower(Project.name) == func.lower(project_name)).first()
        if not project:
            await update.message.reply_text(f"❗️ Проект '{project_name}' не найден.")
            return
            
        db.session.delete(project)
        db.session.commit()
        
    await update.message.reply_text(f"🗑️ Проект '{project_name}' и все связанные с ним задачи удалены.")

# --- 5. ГЛАВНАЯ ФУНКЦИЯ ---
def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("inbox", inbox_command))
    application.add_handler(CommandHandler("projects", projects_command))
    application.add_handler(CommandHandler("add", add_task))
    # --- НОВЫЕ КОМАНДЫ ---
    application.add_handler(CommandHandler("add_project", add_project_command))
    application.add_handler(CommandHandler("delete_project", delete_project_command))
    
    print("Бот запущен и подключен к базе данных...")
    application.run_polling()

if __name__ == "__main__":
    main()