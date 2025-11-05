# database.py

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, func, inspect, Table
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Date, ForeignKey, Numeric

load_dotenv()

DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_URI = f"postgresql://planner_user:{DB_PASSWORD}@localhost:5432/planner_db"

engine = create_engine(DB_URI)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- ВАЖНО: Мы удаляем эти таблицы, чтобы вернуться к версии без тегов ---
# task_tags = Table(...)
# class Tag(Base): ...

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
    
    # --- ВАЖНО: Мы удаляем связь с тегами ---
    # tags = relationship(...)

class ActivityLog(Base):
    __tablename__ = 'activity_log'
    id = Column(Integer, primary_key=True)
    description = Column(Text, nullable=False)
    duration_hours = Column(Numeric(5, 2), nullable=False)
    activity_date = Column(Date, nullable=False)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)

def init_db():
    inspector = inspect(engine)
    if not inspector.has_table("tasks"):
        print("База данных не найдена или пуста. Создаю таблицы...")
        Base.metadata.create_all(bind=engine)
        print("✅ Таблицы успешно созданы.")
    else:
        print("✅ База данных уже настроена.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'init':
        init_db()
    else:
        print("Использование: python database.py init")