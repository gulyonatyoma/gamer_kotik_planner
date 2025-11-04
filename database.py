# database.py

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, func, inspect
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Date, ForeignKey, Numeric
from sqlalchemy.orm import relationship

# Загружаем переменные окружения из .env файла
load_dotenv()

# --- 1. Настройка подключения ---
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_URI = f"postgresql://planner_user:{DB_PASSWORD}@localhost:5432/planner_db"

engine = create_engine(DB_URI)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- 2. Модели (без изменений) ---

class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    tasks = relationship('Task', backref='project', lazy=True, cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    status = Column(String(50), default='pending')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    is_today = Column(Boolean, default=False)
    priority = Column(String(50), default='low')
    deadline = Column(Date, nullable=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)

class ActivityLog(Base):
    __tablename__ = 'activity_log'
    id = Column(Integer, primary_key=True)
    description = Column(Text, nullable=False)
    duration_hours = Column(Numeric(5, 2), nullable=False)
    activity_date = Column(Date, nullable=False)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)


# --- НОВАЯ УМНАЯ ФУНКЦИЯ ИНИЦИАЛИЗАЦИИ ---

def init_db():
    """
    Проверяет, существуют ли таблицы в базе данных.
    Если нет - создает их.
    """
    inspector = inspect(engine)
    # Проверяем наличие одной из таблиц (этого достаточно)
    if not inspector.has_table("tasks"):
        print("База данных не найдена или пуста. Создаю таблицы...")
        Base.metadata.create_all(bind=engine)
        print("✅ Таблицы успешно созданы.")
    else:
        print("✅ База данных уже настроена.")


# Эта часть позволяет вызывать init_db из командной строки
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'init':
        init_db()
    else:
        print("Использование: python database.py init")