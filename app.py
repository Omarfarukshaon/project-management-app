import os
import csv
from io import StringIO
from flask import Flask, render_template, request, redirect, url_for, session, Response
import sqlite3
from datetime import date, timedelta
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'super_secret_project_key' 

app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect('project_manager.db', timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

# Automatically upgrades database schema to support per-developer task progress tracking & priority
def upgrade_database_schema():
    conn = sqlite3.connect('project_manager.db')
    try:
        conn.execute('ALTER TABLE task_assignments ADD COLUMN progress INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass 
    try:
        conn.execute('ALTER TABLE tasks ADD COLUMN progress INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE tasks ADD COLUMN priority TEXT DEFAULT 'Medium'")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

upgrade_database_schema()

def log_activity(user_id):
    try:
        conn = get_db_connection()
        today = date.today().strftime('%Y-%m-%d')
        row = conn.execute('SELECT count FROM activities WHERE user_id = ? AND date = ?', (user_id, today)).fetchone()
        
        if row:
            conn.execute('UPDATE activities SET count = count + 1 WHERE user_id = ? AND date = ?', (user_id, today))
        else:
            conn.execute('INSERT INTO activities (user_id, date, count) VALUES (?, ?, 1)', (user_id, today))
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Activity logging error: {e}")

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid username or password. Please try again."
            
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear() 
    return redirect(url_for('login'))

@app.route('/')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    current_user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    
    if user_role == 'admin':
        projects = conn.execute('SELECT * FROM projects ORDER BY id DESC LIMIT 7').fetchall()
        dashboard_title = "Global Project Overview (Admin)"
    elif user_role == 'manager':
        projects = conn.execute('SELECT * FROM projects WHERE manager_id = ? ORDER BY id DESC LIMIT 7', (user_id,)).fetchall()
        dashboard_title = "My Managed Projects"
    else:
        projects = conn.execute('''
            SELECT DISTINCT projects.* 
            FROM projects 
            JOIN tasks ON projects.id = tasks.project_id 
            JOIN task_assignments ON tasks.id = task_assignments.task_id
            WHERE task_assignments.developer_id = ?
            ORDER BY projects.id DESC LIMIT 7
        ''', (user_id,)).fetchall()
        dashboard_title = "My Assigned Projects"

      
    activities = conn.execute('SELECT date, count FROM activities WHERE user_id = ?', (user_id,)).fetchall()
    activity_dict = {row['date']: row['count'] for row in activities}
    
    today = date.today()
    days = []
    for i in range(140, -1, -1):
        d = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        count = activity_dict.get(d, 0)
        
        level = 0
        if count > 0: level = 1
        if count >= 3: level = 2
        if count >= 5: level = 3
        if count >= 7: level = 4
            
        days.append({'date': d, 'level': level, 'count': count})
        
    conn.close()
    return render_template('dashboard.html', projects=projects, role=user_role, user=current_user, dashboard_title=dashboard_title, days=days)

@app.route('/projects')
def project_list():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    user_role = session.get('role')
    user_id = session.get('user_id')
    search_query = request.args.get('q', '').strip()
    
    if user_role == 'admin':
        if search_query:
            projects = conn.execute('SELECT * FROM projects WHERE title LIKE ? ORDER BY id DESC', ('%' + search_query + '%',)).fetchall()
        else:
            projects = conn.execute('SELECT * FROM projects ORDER BY id DESC').fetchall()
    elif user_role == 'manager':
        if search_query:
            projects = conn.execute('SELECT * FROM projects WHERE manager_id = ? AND title LIKE ? ORDER BY id DESC', (user_id, '%' + search_query + '%')).fetchall()
        else:
            projects = conn.execute('SELECT * FROM projects WHERE manager_id = ? ORDER BY id DESC', (user_id,)).fetchall()
    else:
        if search_query:
            projects = conn.execute('''
                SELECT DISTINCT projects.* FROM projects 
                JOIN tasks ON projects.id = tasks.project_id 
                JOIN task_assignments ON tasks.id = task_assignments.task_id
                WHERE task_assignments.developer_id = ? AND projects.title LIKE ? ORDER BY projects.id DESC
            ''', (user_id, '%' + search_query + '%')).fetchall()
        else:
            projects = conn.execute('''
                SELECT DISTINCT projects.* FROM projects 
                JOIN tasks ON projects.id = tasks.project_id 
                JOIN task_assignments ON tasks.id = task_assignments.task_id
                WHERE task_assignments.developer_id = ? ORDER BY projects.id DESC
            ''', (user_id,)).fetchall()
        
    conn.close()
    return render_template('projects_list.html', projects=projects, role=user_role, search_query=search_query)

@app.route('/admin/activities')
def admin_activities():
    if session.get('role') != 'admin':
        return "Access Denied.", 403
        
    conn = get_db_connection()
    users_activity = conn.execute('''
        SELECT users.id, users.username, users.full_name, users.role, SUM(activities.count) as total_activity 
        FROM users 
        LEFT JOIN activities ON users.id = activities.user_id 
        GROUP BY users.id
    ''').fetchall()
    conn.close()
    return render_template('admin_activities.html', users_activity=users_activity)

@app.route('/admin/user/<int:user_id>/activities')
def user_activity_detail(user_id):
    if session.get('role') != 'admin':
        return "Access Denied.", 403
        
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    activities = conn.execute('SELECT date, count FROM activities WHERE user_id = ? ORDER BY date DESC', (user_id,)).fetchall()
    conn.close()
    
    return render_template('user_activity_detail.html', user=user, activities=activities, role=session.get('role'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    error = None
    success = None
    
    if request.method == 'POST':
        if 'update_profile' in request.form:
            full_name = request.form['full_name']
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')
            image = request.files.get('profile_image')
 
            if image and image.filename != '':
                filename = secure_filename(image.filename)
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                conn.execute('UPDATE users SET full_name = ?, profile_image = ? WHERE id = ?', (full_name, filename, user_id))
            else:
                conn.execute('UPDATE users SET full_name = ? WHERE id = ?', (full_name, user_id))
            
            if new_password.strip() != '':
                user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
                if user['password'] != current_password:
                    error = "Incorrect current password. Password was not changed."
                elif new_password != confirm_password:
                    error = "New passwords do not match."
                else:
                    conn.execute('UPDATE users SET password = ? WHERE id = ?', (new_password, user_id))
                    success = "Profile and password updated successfully!"
            else:
                success = "Profile updated successfully!"
                
            conn.commit()
        
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    current_user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    
    return render_template('profile.html', user=user, role=session.get('role'), current_user=current_user, error=error, success=success)

@app.route('/project/<int:project_id>', methods=['GET', 'POST'])
def project_detail(project_id):
    if 'username' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    if request.method == 'POST':
        if 'project_comment' in request.form:
            content = request.form['project_comment']
            author = session.get('username')
            conn.execute('INSERT INTO project_comments (project_id, author, content) VALUES (?, ?, ?)',
                         (project_id, author, content))
        elif 'add_developer' in request.form and user_role in ['admin', 'manager']:
            new_dev_id = request.form['new_developer_id']
            exists = conn.execute('SELECT 1 FROM project_teams WHERE project_id = ? AND developer_id = ?', (project_id, new_dev_id)).fetchone()
            if not exists:
                conn.execute('INSERT INTO project_teams (project_id, developer_id) VALUES (?, ?)', (project_id, new_dev_id))
        elif 'remove_developer_id' in request.form and user_role in ['admin', 'manager']:
            remove_dev_id = request.form['remove_developer_id']
            conn.execute('DELETE FROM project_teams WHERE project_id = ? AND developer_id = ?', (project_id, remove_dev_id))
        
        conn.commit()
        return redirect(url_for('project_detail', project_id=project_id))
    
    project = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        conn.close()
        return "Project not found.", 404

    if user_role == 'manager' and project['manager_id'] != user_id:
        conn.close()
        return "Access Denied: You do not own this project.", 403
    elif user_role == 'developer':
        assigned_check = conn.execute('''
            SELECT * FROM project_teams WHERE project_id = ? AND developer_id = ?
        ''', (project_id, user_id)).fetchone()
        
        if not assigned_check:
            fallback = conn.execute('''
                SELECT * FROM tasks t JOIN task_assignments ta ON t.id = ta.task_id 
                WHERE t.project_id = ? AND ta.developer_id = ?
            ''', (project_id, user_id)).fetchone()
            if not fallback:
                conn.close()
                return "Access Denied: You are not assigned to this project.", 403

    conn.execute('''
        INSERT INTO project_teams (project_id, developer_id)
        SELECT DISTINCT t.project_id, ta.developer_id
        FROM tasks t JOIN task_assignments ta ON t.id = ta.task_id
        WHERE t.project_id = ? AND ta.developer_id NOT IN (SELECT developer_id FROM project_teams WHERE project_id = ?)
    ''', (project_id, project_id))
    conn.commit()

    if user_role in ['admin', 'manager']:
        tasks = conn.execute('SELECT * FROM tasks WHERE project_id = ?', (project_id,)).fetchall()
    else:
        tasks = conn.execute('''
            SELECT DISTINCT t.* FROM tasks t 
            JOIN task_assignments ta ON t.id = ta.task_id 
            WHERE t.project_id = ? AND ta.developer_id = ?
        ''', (project_id, user_id)).fetchall()

    task_progress_list = []
    for t in tasks:
        avg_prog = conn.execute('SELECT AVG(progress) as avg_p FROM task_assignments WHERE task_id = ?', (t['id'],)).fetchone()['avg_p']
        t_prog = int(avg_prog) if avg_prog is not None else t['progress']
        task_progress_list.append(t_prog)

    total_progress = sum(task_progress_list) if task_progress_list else 0
    progress_percentage = int(total_progress / len(tasks)) if tasks else 0

    manager_details = conn.execute('SELECT id, username, full_name, profile_image, role FROM users WHERE id = ?', (project['manager_id'],)).fetchone()

    team_members = conn.execute('''
        SELECT u.id, u.username, u.full_name, u.profile_image, u.role,
               COUNT(t.id) as total_tasks,
               COALESCE(SUM(CASE WHEN ta.progress = 100 THEN 1 ELSE 0 END), 0) as completed_tasks
        FROM project_teams pt
        JOIN users u ON pt.developer_id = u.id
        LEFT JOIN task_assignments ta ON u.id = ta.developer_id
        LEFT JOIN tasks t ON ta.task_id = t.id AND t.project_id = pt.project_id
        WHERE pt.project_id = ?
        GROUP BY u.id
    ''', (project_id,)).fetchall()

    available_devs = conn.execute('''
        SELECT id, username, full_name FROM users 
        WHERE role = 'developer' AND id NOT IN (
            SELECT developer_id FROM project_teams WHERE project_id = ?
        )
    ''', (project_id,)).fetchall()

    project_comments = conn.execute('SELECT * FROM project_comments WHERE project_id = ? ORDER BY timestamp DESC', (project_id,)).fetchall()
        
    conn.close()
    today = date.today().strftime('%Y-%m-%d')
    
    tasks_with_progress = []
    conn = get_db_connection()
    for t in tasks:
        avg = conn.execute('SELECT AVG(progress) as avg_p FROM task_assignments WHERE task_id = ?', (t['id'],)).fetchone()['avg_p']
        p_val = int(avg) if avg is not None else t['progress']
        t_dict = dict(t)
        t_dict['progress'] = p_val
        tasks_with_progress.append(t_dict)
    conn.close()

    return render_template('project_detail.html', project=project, tasks=tasks_with_progress, today=today, role=user_role, 
                           progress_percentage=progress_percentage, team_members=team_members, 
                           manager_details=manager_details, available_devs=available_devs, project_comments=project_comments)

@app.route('/add', methods=('GET', 'POST'))
def add_project():
    if session.get('role') != 'admin':
        return "Access Denied. Only Admins can create projects.", 403

    conn = get_db_connection()
    if request.method == 'POST':
        project_title = request.form['project_title']
        project_deadline = request.form['project_deadline']
        manager_id = request.form['manager_id'] 

        cursor = conn.cursor()
        cursor.execute('INSERT INTO projects (title, manager_id, deadline) VALUES (?, ?, ?)',
                       (project_title, manager_id, project_deadline))
        conn.commit()
        conn.close()
        
        log_activity(session['user_id'])
        return redirect(url_for('dashboard'))
    
    managers = conn.execute("SELECT * FROM users WHERE role = 'manager'").fetchall()
    conn.close()
    return render_template('add_project.html', managers=managers)

@app.route('/project/<int:project_id>/add_task', methods=('GET', 'POST'))
def add_task(project_id):
    if session.get('role') not in ['admin', 'manager']:
        return "Access Denied.", 403

    conn = get_db_connection()
    if request.method == 'POST':
        task_title = request.form['task_title']
        task_deadline = request.form['task_deadline']
        priority = request.form.get('priority', 'Medium')
        assigned_developers = request.form.getlist('developer_ids') 

        cursor = conn.cursor()
        cursor.execute('INSERT INTO tasks (project_id, title, deadline, is_completed, progress, priority) VALUES (?, ?, ?, ?, ?, ?)',
                       (project_id, task_title, task_deadline, 0, 0, priority))
        task_id = cursor.lastrowid
        
        for dev_id in assigned_developers:
            cursor.execute('INSERT INTO task_assignments (task_id, developer_id, progress) VALUES (?, ?, 0)', (task_id, dev_id))
            
        conn.commit()
        conn.close()
        log_activity(session['user_id'])
        return redirect(url_for('project_detail', project_id=project_id))
    
    developers = conn.execute("SELECT * FROM users WHERE role = 'developer'").fetchall()
    project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    
    return render_template('add_task.html', project=project, developers=developers)

@app.route('/admin/users', methods=['GET', 'POST'])
def manage_users():
    if session.get('role') != 'admin':
        return "Access Denied.", 403
    conn = get_db_connection()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        full_name = request.form.get('full_name', '')
        try:
            conn.execute('INSERT INTO users (username, password, role, full_name, profile_image) VALUES (?, ?, ?, ?, "default.png")',
                         (username, password, role, full_name))
            conn.commit()
        except sqlite3.IntegrityError:
            pass 
        return redirect(url_for('manage_users'))

    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    return render_template('manage_users.html', users=users, role=session.get('role'))

@app.route('/task/<int:task_id>', methods=('GET', 'POST'))
def task_detail(task_id):
    conn = get_db_connection()
    
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not task:
        conn.close()
        return "Task not found", 404
        
    user_id = session.get('user_id')
    user_role = session.get('role')
    
    if request.method == 'POST':
        if 'update_progress' in request.form:
            new_progress = int(request.form['progress_value'])
            progress_note = request.form.get('progress_note', '').strip()
            
            if user_role == 'developer':
                conn.execute('UPDATE task_assignments SET progress = ? WHERE task_id = ? AND developer_id = ?', 
                             (new_progress, task_id, user_id))
            else:
                conn.execute('UPDATE task_assignments SET progress = ? WHERE task_id = ?', (new_progress, task_id))
            
            avg_res = conn.execute('SELECT AVG(progress) as avg_p FROM task_assignments WHERE task_id = ?', (task_id,)).fetchone()
            overall_prog = int(avg_res['avg_p']) if avg_res['avg_p'] is not None else new_progress
            is_comp = 1 if overall_prog == 100 else 0
            conn.execute('UPDATE tasks SET progress = ?, is_completed = ? WHERE id = ?', (overall_prog, is_comp, task_id))
            
            if progress_note:
                author = session.get('username')
                formatted_comment = f"[Progress Update -> {new_progress}% by {author}]: {progress_note}"
                conn.execute('INSERT INTO comments (task_id, content, author) VALUES (?, ?, ?)', (task_id, formatted_comment, author))
                
            should_log = True
        elif 'comment_content' in request.form:
            comment_content = request.form['comment_content']
            author = session.get('username') 
            conn.execute('INSERT INTO comments (task_id, content, author) VALUES (?, ?, ?)', (task_id, comment_content, author))
            should_log = True
        elif 'add_assignee_id' in request.form:
            if user_role in ['admin', 'manager']:
                new_dev_id = request.form['add_assignee_id']
                exists = conn.execute('SELECT 1 FROM task_assignments WHERE task_id = ? AND developer_id = ?', (task_id, new_dev_id)).fetchone()
                if not exists:
                    conn.execute('INSERT INTO task_assignments (task_id, developer_id, progress) VALUES (?, ?, 0)', (task_id, new_dev_id))
            should_log = False
        elif 'remove_assignee_id' in request.form:
            if user_role in ['admin', 'manager']:
                remove_dev_id = request.form['remove_assignee_id']
                conn.execute('DELETE FROM task_assignments WHERE task_id = ? AND developer_id = ?', (task_id, remove_dev_id))
            should_log = False
        else:
            should_log = False
                
        conn.commit()
        if should_log:
            log_activity(session['user_id'])
        conn.close()
        return redirect(url_for('task_detail', task_id=task_id))

    comments = conn.execute('SELECT * FROM comments WHERE task_id = ? ORDER BY timestamp DESC', (task_id,)).fetchall()
    
    assigned_devs = conn.execute('''
        SELECT u.id, u.username, u.full_name, u.profile_image, ta.progress 
        FROM users u 
        JOIN task_assignments ta ON u.id = ta.developer_id 
        WHERE ta.task_id = ?
    ''', (task_id,)).fetchall()
    
    my_progress = 0
    if user_role == 'developer':
        my_row = conn.execute('SELECT progress FROM task_assignments WHERE task_id = ? AND developer_id = ?', (task_id, user_id)).fetchone()
        if my_row:
            my_progress = my_row['progress']
    else:
        my_progress = task['progress']

    available_devs = conn.execute('''
        SELECT id, username, full_name 
        FROM users 
        WHERE role = 'developer' AND id NOT IN (
            SELECT developer_id FROM task_assignments WHERE task_id = ?
        )
    ''', (task_id,)).fetchall()
    
    today = date.today().strftime('%Y-%m-%d')
    conn.close()
    
    return render_template('task_detail.html', task=task, comments=comments, 
                           assigned_devs=assigned_devs, available_devs=available_devs, 
                           role=user_role, username=session.get('username'), my_progress=my_progress, today=today)

@app.route('/generate_report')
def generate_report():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_role = session.get('role')
    user_id = session.get('user_id')
    conn = get_db_connection()
    
    si = StringIO()
    cw = csv.writer(si)
    
    if user_role == 'admin':
        cw.writerow(['Project ID', 'Project Title', 'Manager ID', 'Deadline', 'Status'])
        projects = conn.execute('SELECT * FROM projects').fetchall()
        for p in projects:
            cw.writerow([p['id'], p['title'], p['manager_id'], p['deadline'], p['status']])
        filename = "Admin_Global_Report.csv"
        
    elif user_role == 'manager':
        cw.writerow(['Project ID', 'Project Title', 'Deadline', 'Status'])
        projects = conn.execute('SELECT * FROM projects WHERE manager_id = ?', (user_id,)).fetchall()
        for p in projects:
            cw.writerow([p['id'], p['title'], p['deadline'], p['status']])
        filename = "Manager_Projects_Report.csv"
        
    else:
        cw.writerow(['Task ID', 'Task Title', 'Project Name', 'Deadline', 'Priority', 'My Progress (%)'])
        tasks = conn.execute('''
            SELECT t.id, t.title, p.title as proj_title, t.deadline, t.priority, ta.progress 
            FROM tasks t 
            JOIN task_assignments ta ON t.id = ta.task_id 
            JOIN projects p ON t.project_id = p.id
            WHERE ta.developer_id = ?
        ''', (user_id,)).fetchall()
        for t in tasks:
            cw.writerow([t['id'], t['title'], t['proj_title'], t['deadline'], t['priority'], t['progress']])
        filename = "Developer_Tasks_Report.csv"
        
    conn.close()
    
    output = Response(si.getvalue(), mimetype='text/csv')
    output.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return output

if __name__ == '__main__':
    app.run(debug=True)