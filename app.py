# app.py

import os
from datetime import datetime, date, timedelta
import calendar
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

# --- 1. Настройка ---
app = Flask(__name__)

# !!! ВАЖНО: ЗАМЕНИТЕ 'Yfnfif1999!' НА ВАШ ПАРОЛЬ ДЛЯ planner_user !!!
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'Yfnfif1999!')
DB_URI = f"postgresql://planner_user:{DB_PASSWORD}@localhost:5432/planner_db"

app.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- 2. Модели ---
class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    tasks = db.relationship('Task', backref='project', lazy=True, cascade="all, delete-orphan")

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    is_today = db.Column(db.Boolean, default=False)
    priority = db.Column(db.String(50), default='low')
    deadline = db.Column(db.Date, nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)

class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text, nullable=False)
    duration_hours = db.Column(db.Numeric(5, 2), nullable=False)
    activity_date = db.Column(db.Date, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)

# --- 3. Создание таблиц ---
with app.app_context():
    db.create_all()

# --- Вспомогательные функции ---
@app.template_filter('format_datetime')
def _format_datetime(value, format='%A, %d %B %Y'):
    if value == 'now': return datetime.now().strftime(format)
    if isinstance(value, (datetime, date)): return value.strftime(format)
    try: return datetime.fromisoformat(value).strftime(format)
    except (ValueError, TypeError): return value

def get_nav_data():
    inbox_count = Task.query.filter_by(status='pending', is_today=False, project_id=None).count()
    return {'inbox_count': inbox_count}

# --- Маршруты (Страницы) ---
@app.route('/')
def index():
    inbox_tasks = Task.query.filter_by(status='pending', is_today=False, project_id=None).order_by(Task.created_at).all()
    today_tasks_q = Task.query.filter_by(status='pending', is_today=True)
    priority_map = {"high": 0, "medium": 1, "low": 2}
    today_tasks = sorted(today_tasks_q, key=lambda x: priority_map.get(x.priority, 2))
    all_task_titles = [t.title for t in Task.query.distinct(Task.title).all()]
    all_projects = [p.name for p in Project.query.order_by(Project.name).all()]
    return render_template('index.html', inbox_tasks=inbox_tasks, today_tasks=today_tasks, today_date=date.today().isoformat(), nav_data=get_nav_data(), all_task_titles=all_task_titles, all_projects=all_projects)

@app.route('/projects')
def projects_page():
    all_projects = Project.query.order_by(Project.name).all()
    projects_data = []
    for p in all_projects:
        total = len(p.tasks)
        completed = Task.query.filter_by(project_id=p.id, status='completed').count()
        progress = int((completed / total) * 100) if total > 0 else 0
        projects_data.append({'id': p.id, 'name': p.name, 'total': total, 'completed': completed, 'progress': progress})
    return render_template('projects.html', projects=projects_data, nav_data=get_nav_data())

@app.route('/project/<project_name>')
def project_detail_page(project_name):
    project = Project.query.filter_by(name=project_name).first_or_404()
    project_tasks = Task.query.filter_by(project_id=project.id, status='pending').order_by(Task.created_at).all()
    return render_template('project_detail.html', project_name=project.name, tasks=project_tasks, today_date=date.today().isoformat(), nav_data=get_nav_data())

@app.route('/archive')
def archive_page():
    completed_tasks = Task.query.filter_by(status='completed').order_by(Task.completed_at.desc()).all()
    return render_template('archive.html', tasks=completed_tasks, nav_data=get_nav_data())

@app.route('/calendar', defaults={'year': None, 'month': None})
@app.route('/calendar/<int:year>/<int:month>')
def calendar_page(year, month):
    if year is None or month is None: 
        target_date = date.today()
    else: 
        target_date = date(year, month, 1)

    prev = target_date.replace(day=1) - timedelta(days=1)
    next = (target_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    nav = {'prev': {'year': prev.year, 'month': prev.month}, 'next': {'year': next.year, 'month': next.month}}
    
    cal = calendar.Calendar()
    month_days = cal.monthdatescalendar(target_date.year, target_date.month)
    
    # Получаем все задачи с дедлайнами из БД
    tasks_with_deadline = Task.query.filter(Task.deadline != None).all()
    
    tasks_by_date = {}
    for task in tasks_with_deadline:
        deadline_str = task.deadline.isoformat()
        if deadline_str not in tasks_by_date:
            tasks_by_date[deadline_str] = []
        tasks_by_date[deadline_str].append(task)
        
    return render_template('calendar.html', 
                           month_days=month_days, 
                           tasks_by_date=tasks_by_date, 
                           today=date.today(), 
                           current_month_date=target_date, 
                           nav=nav, 
                           nav_data=get_nav_data())
@app.route('/review')
def review_page():
    today = date.today(); start_of_week = today - timedelta(days=today.weekday())
    labels = [(start_of_week + timedelta(days=i)).strftime('%a, %d') for i in range(7)]
    data = [0] * 7
    completed_this_week = Task.query.filter(Task.status=='completed', Task.completed_at >= start_of_week, Task.completed_at < start_of_week + timedelta(days=7)).all()
    for task in completed_this_week:
        data[task.completed_at.weekday()] += 1
    return render_template('review.html', labels=labels, data=data, total_completed=len(completed_this_week), nav_data=get_nav_data())

# --- ИСПРАВЛЕННАЯ ФУНКЦИЯ АНАЛИТИКИ ---
@app.route('/analytics')
def analytics_page():
    activities = ActivityLog.query.order_by(ActivityLog.activity_date).all()
    
    tasks_time = {}
    for activity in activities:
        desc = activity.description
        if desc not in tasks_time:
            tasks_time[desc] = []
        tasks_time[desc].append({
            'date': activity.activity_date,
            'duration': float(activity.duration_hours) # Преобразуем из Decimal
        })

    # Готовим данные для графика
    datasets = []
    all_dates_q = db.session.query(ActivityLog.activity_date).distinct().order_by(ActivityLog.activity_date)
    all_dates = [d[0] for d in all_dates_q]
    
    if not all_dates: # Если активностей еще нет, показываем пустую страницу
        return render_template('analytics.html', labels=[], datasets=[], nav_data=get_nav_data())

    for task_name, acts in tasks_time.items():
        cumulative_time = 0
        data_points = {}
        for act in acts:
            cumulative_time += act['duration']
            data_points[act['date']] = cumulative_time

        final_data = []; last_known_value = 0
        min_date_for_task = min(data_points.keys())
        for d in all_dates:
            if d in data_points:
                last_known_value = data_points[d]
            if d >= min_date_for_task:
                final_data.append(last_known_value)
            else:
                final_data.append(0)
        
        datasets.append({
            'label': task_name,
            'data': final_data,
            'fill': False,
            'tension': 0.1,
            'borderColor': f'hsl({(hash(task_name) % 360)}, 70%, 50%)',
            'backgroundColor': f'hsla({(hash(task_name) % 360)}, 70%, 50%, 0.1)'
        })
    
    labels = [d.strftime('%d.%m') for d in all_dates]
    return render_template('analytics.html', labels=labels, datasets=datasets, nav_data=get_nav_data())

# --- Маршруты (Действия) ---
@app.route('/add_task', methods=['POST'])
def add_task():
    title = request.form.get('title', '').strip()
    deadline_str = request.form.get('deadline')
    if not title: return redirect(url_for('index'))
    deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None
    # Задачи, добавленные с главной, попадают в "План на сегодня" и не имеют проекта
    new_task = Task(title=title, deadline=deadline, project_id=None, is_today=True)
    db.session.add(new_task)
    db.session.commit()
    return redirect(url_for('index'))
    
@app.route('/add_project', methods=['POST'])
def add_project():
    project_name = request.form.get('project_name', '').strip()
    if not project_name: return redirect(url_for('projects_page'))
    if not Project.query.filter_by(name=project_name).first():
        new_project = Project(name=project_name)
        db.session.add(new_project)
        db.session.add(Task(title="Начать работу над проектом", project=new_project))
        db.session.commit()
    return redirect(url_for('projects_page'))

@app.route('/add_task_to_project/<project_name>', methods=['POST'])
def add_task_to_project(project_name):
    title = request.form.get('title', '').strip()
    deadline_str = request.form.get('deadline')
    if not title: return redirect(url_for('project_detail_page', project_name=project_name))
    project = Project.query.filter_by(name=project_name).first_or_404()
    deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None
    new_task = Task(title=title, deadline=deadline, project_id=project.id)
    db.session.add(new_task)
    db.session.commit()
    return redirect(url_for('project_detail_page', project_name=project_name))

@app.route('/log_activity', methods=['POST'])
def log_activity():
    description = request.form.get('description', '').strip()
    duration_str = request.form.get('duration')
    project_name = request.form.get('project', '').strip().lstrip('#')
    if not (description and duration_str): return redirect(url_for('index'))
    
    project_id = None
    if project_name:
        project = Project.query.filter_by(name=project_name).first()
        if project: project_id = project.id

    new_activity = ActivityLog(
        description=description,
        duration_hours=float(duration_str),
        activity_date=date.today(),
        project_id=project_id
    )
    db.session.add(new_activity)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/complete_task/<int:task_id>', methods=['POST'])
def complete_task(task_id):
    task = db.session.get(Task, task_id)
    if task:
        task.status = 'completed'; task.completed_at = datetime.utcnow(); task.is_today = False
        db.session.commit()
    return redirect(request.referrer or url_for('index'))

@app.route('/delete_task/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    task = db.session.get(Task, task_id)
    if task:
        db.session.delete(task)
        db.session.commit()
    return redirect(request.referrer or url_for('index'))

@app.route('/move_to_today/<int:task_id>', methods=['POST'])
def move_to_today(task_id):
    task = db.session.get(Task, task_id)
    if task:
        task.is_today = True
        db.session.commit()
    return redirect(request.referrer or url_for('index'))

@app.route('/set_priority/<int:task_id>', methods=['POST'])
def set_priority(task_id):
    task = db.session.get(Task, task_id)
    if task:
        priorities = ["low", "medium", "high"]
        current_priority = task.priority or 'low'
        current_index = priorities.index(current_priority)
        new_index = (current_index + 1) % len(priorities)
        task.priority = priorities[new_index]
        db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)