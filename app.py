# app.py

import os
from datetime import datetime, date, timedelta
import calendar
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, select
from dotenv import load_dotenv

from database import DB_URI, Project, Task, ActivityLog

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

with app.app_context():
    db.create_all()

@app.template_filter('format_datetime')
def _format_datetime(value, format='%A, %d %B %Y'):
    if value == 'now': return datetime.now().strftime(format)
    if isinstance(value, (datetime, date)): return value.strftime(format)
    try: return datetime.fromisoformat(value).strftime(format)
    except (ValueError, TypeError): return value

def get_nav_data():
    inbox_count = db.session.scalar(
        select(func.count(Task.id)).filter_by(status='pending', is_today=False, project_id=None)
    )
    return {'inbox_count': inbox_count}

@app.route('/')
def index():
    inbox_tasks = db.session.execute(select(Task).filter_by(status='pending', is_today=False, project_id=None).order_by(Task.created_at)).scalars().all()
    today_tasks_q = db.session.execute(select(Task).filter_by(status='pending', is_today=True)).scalars().all()
    priority_map = {"high": 0, "medium": 1, "low": 2}
    today_tasks = sorted(today_tasks_q, key=lambda x: priority_map.get(x.priority, 2))
    all_task_titles_q = db.session.execute(select(Task.title).distinct()).scalars().all()
    all_projects_q = db.session.execute(select(Project.name).order_by(Project.name)).scalars().all()
    return render_template('index.html', inbox_tasks=inbox_tasks, today_tasks=today_tasks, today_date=date.today(), nav_data=get_nav_data(), all_task_titles=all_task_titles_q, all_projects=all_projects_q)

@app.route('/projects')
def projects_page():
    all_projects = db.session.execute(select(Project).order_by(Project.name)).scalars().all()
    projects_data = []
    for p in all_projects:
        total = len(p.tasks)
        completed = db.session.scalar(select(func.count(Task.id)).filter_by(project_id=p.id, status='completed'))
        progress = int((completed / total) * 100) if total > 0 else 0
        projects_data.append({'id': p.id, 'name': p.name, 'total': total, 'completed': completed, 'progress': progress})
    return render_template('projects.html', projects=projects_data, nav_data=get_nav_data())

# --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
@app.route('/project/<project_name>')
def project_detail_page(project_name):
    # Используем правильный и самый надежный способ получить объект или ошибку 404
    project = db.session.execute(select(Project).filter_by(name=project_name)).scalar_one()
    
    project_tasks = db.session.execute(select(Task).filter_by(project_id=project.id, status='pending').order_by(Task.created_at)).scalars().all()
    return render_template('project_detail.html', project=project, tasks=project_tasks, today_date=date.today(), nav_data=get_nav_data())

@app.route('/archive')
def archive_page():
    completed_tasks = db.session.execute(select(Task).order_by(Task.completed_at.desc()).filter_by(status='completed')).scalars().all()
    return render_template('archive.html', tasks=completed_tasks, nav_data=get_nav_data())

# ... (остальной код файла app.py остается без изменений) ...
@app.route('/calendar', defaults={'year': None, 'month': None})
@app.route('/calendar/<int:year>/<int:month>')
def calendar_page(year, month):
    if year is None or month is None: target_date = date.today()
    else: target_date = date(year, month, 1)
    prev = target_date.replace(day=1) - timedelta(days=1)
    next_month_date = (target_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    nav = {'prev': {'year': prev.year, 'month': prev.month}, 'next': {'year': next_month_date.year, 'month': next_month_date.month}}
    cal = calendar.Calendar()
    month_days = cal.monthdatescalendar(target_date.year, target_date.month)
    tasks_with_deadline = db.session.execute(select(Task).filter(Task.deadline != None)).scalars().all()
    tasks_by_date = {}
    for task in tasks_with_deadline:
        if task.deadline:
            deadline_str = task.deadline.isoformat()
            if deadline_str not in tasks_by_date: tasks_by_date[deadline_str] = []
            tasks_by_date[deadline_str].append(task)
    return render_template('calendar.html', month_days=month_days, tasks_by_date=tasks_by_date, today=date.today(), current_month_date=target_date, nav=nav, nav_data=get_nav_data())

@app.route('/review')
def review_page():
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    labels = [(start_of_week + timedelta(days=i)).strftime('%a, %d') for i in range(7)]
    data = [0] * 7
    completed_this_week = db.session.execute(select(Task).filter(Task.status=='completed', Task.completed_at >= start_of_week, Task.completed_at < start_of_week + timedelta(days=7))).scalars().all()
    for task in completed_this_week:
        if task.completed_at: data[task.completed_at.weekday()] += 1
    return render_template('review.html', labels=labels, data=data, total_completed=len(completed_this_week), nav_data=get_nav_data())

@app.route('/analytics')
def analytics_page():
    activities = db.session.execute(select(ActivityLog).order_by(ActivityLog.activity_date)).scalars().all()
    tasks_time = {}
    for activity in activities:
        desc = activity.description
        if desc not in tasks_time: tasks_time[desc] = []
        tasks_time[desc].append({'date': activity.activity_date, 'duration': float(activity.duration_hours)})
    datasets = []
    all_dates_q = db.session.execute(select(ActivityLog.activity_date).distinct().order_by(ActivityLog.activity_date)).scalars().all()
    if not all_dates_q: return render_template('analytics.html', labels=[], datasets=[], nav_data=get_nav_data())
    for task_name, acts in tasks_time.items():
        cumulative_time, data_points = 0, {}
        for act in acts:
            cumulative_time += act['duration']
            data_points[act['date']] = cumulative_time
        final_data, last_known_value = [], 0
        min_date_for_task = min(data_points.keys())
        for d in all_dates_q:
            if d in data_points: last_known_value = data_points[d]
            if d >= min_date_for_task: final_data.append(last_known_value)
            else: final_data.append(0)
        datasets.append({'label': task_name, 'data': final_data, 'fill': False, 'tension': 0.1, 'borderColor': f'hsl({(hash(task_name) % 360)}, 70%, 50%)', 'backgroundColor': f'hsla({(hash(task_name) % 360)}, 70%, 50%, 0.1)'})
    labels = [d.strftime('%d.%m') for d in all_dates_q]
    return render_template('analytics.html', labels=labels, datasets=datasets, nav_data=get_nav_data())

@app.route('/add_task', methods=['POST'])
def add_task():
    title = request.form.get('title', '').strip()
    deadline_str = request.form.get('deadline')
    if not title: return redirect(url_for('index'))
    deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None
    new_task = Task(title=title, deadline=deadline, project_id=None, is_today=True)
    db.session.add(new_task)
    db.session.commit()
    return redirect(url_for('index'))
    
@app.route('/add_project', methods=['POST'])
def add_project():
    project_name = request.form.get('project_name', '').strip()
    if not project_name: return redirect(url_for('projects_page'))
    exists = db.session.execute(select(Project).filter_by(name=project_name)).first()
    if not exists:
        new_project = Project(name=project_name)
        db.session.add(new_project)
        db.session.add(Task(title="Начать работу над проектом", project=new_project))
        db.session.commit()
    return redirect(url_for('projects_page'))

# --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
@app.route('/add_task_to_project/<project_name>', methods=['POST'])
def add_task_to_project(project_name):
    title = request.form.get('title', '').strip()
    deadline_str = request.form.get('deadline')
    if not title: return redirect(url_for('project_detail_page', project_name=project_name))
    
    # Используем правильный синтаксис
    project = db.session.execute(select(Project).filter_by(name=project_name)).scalar_one()
    
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
        project = db.session.execute(select(Project).filter_by(name=project_name)).scalar_one_or_none()
        if project: project_id = project.id
    new_activity = ActivityLog(description=description, duration_hours=float(duration_str), activity_date=date.today(), project_id=project_id)
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