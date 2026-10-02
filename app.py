import os
from flask import Flask, render_template, request, redirect, url_for, session
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
            return "Invalid username or password. Please go back and try again."
    return render_template('login.html')

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
    
    # --- SECURE ROLE-BASED PROJECT FILTERING ---
    if user_role == 'admin':
        projects = conn.execute('SELECT * FROM projects').fetchall()
        dashboard_title = "Global Project Overview (Admin)"
    elif user_role == 'manager':
        projects = conn.execute('SELECT * FROM projects WHERE manager_id = ?', (user_id,)).fetchall()
        dashboard_title = "My Managed Projects"
    else:
        projects = conn.execute('''
            SELECT DISTINCT projects.* 
            FROM projects 
            JOIN tasks ON projects.id = tasks.project_id 
            WHERE tasks.developer_id = ?
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
    
    return render_template('dashboard.html', projects=projects, 
                           role=user_role, user=current_user,
                           dashboard_title=dashboard_title, days=days)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    
    if request.method == 'POST':
        if 'update_profile' in request.form:
            full_name = request.form['full_name']
            new_password = request.form.get('new_password', '')
            image = request.files.get('profile_image')
            
            if image and image.filename != '':
                filename = secure_filename(image.filename)
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                conn.execute('UPDATE users SET full_name = ?, profile_image = ? WHERE id = ?', (full_name, filename, user_id))
            else:
                conn.execute('UPDATE users SET full_name = ? WHERE id = ?', (full_name, user_id))
            
            if new_password.strip() != '':
                conn.execute('UPDATE users SET password = ? WHERE id = ?', (new_password, user_id))
                
            conn.commit()
            conn.close()
            return redirect(url_for('profile'))
        
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    current_user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    
    return render_template('profile.html', user=user, role=session.get('role'), current_user=current_user)

@app.route('/project/<int:project_id>')
def project_detail(project_id):
    if 'username' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    project = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    
    if not project:
        conn.close()
        return "Project not found.", 404

    if user_role == 'manager':
        if project['manager_id'] != user_id:
            conn.close()
            return "Access Denied: You do not own this project.", 403
    elif user_role == 'developer':
        assigned_check = conn.execute('SELECT * FROM tasks WHERE project_id = ? AND developer_id = ?', (project_id, user_id)).fetchone()
        if not assigned_check:
            conn.close()
            return "Access Denied: You are not assigned to any tasks in this project.", 403

    if user_role == 'admin' or user_role == 'manager':
        tasks = conn.execute('SELECT * FROM tasks WHERE project_id = ?', (project_id,)).fetchall()
    else:
        tasks = conn.execute('SELECT * FROM tasks WHERE project_id = ? AND developer_id = ?', (project_id, user_id)).fetchall()
        
    conn.close()
    today = date.today().strftime('%Y-%m-%d')
    
    return render_template('project_detail.html', project=project, tasks=tasks, today=today, role=user_role)

@app.route('/add', methods=('GET', 'POST'))
def add_project():
    if session.get('role') not in ['admin', 'manager']:
        return "Access Denied.", 403

    if request.method == 'POST':
        project_title = request.form['project_title']
        project_deadline = request.form['project_deadline']
        task_title = request.form['task_title']
        developer_id = request.form['developer_id']
        task_deadline = request.form['task_deadline']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO projects (title, manager_id, deadline) VALUES (?, ?, ?)',
                       (project_title, session.get('user_id'), project_deadline)) 
        project_id = cursor.lastrowid 
        cursor.execute('INSERT INTO tasks (project_id, developer_id, title, deadline, is_completed) VALUES (?, ?, ?, ?, ?)',
                       (project_id, developer_id, task_title, task_deadline, 0))
        conn.commit()
        conn.close()
        
        log_activity(session['user_id'])
        
        return redirect(url_for('dashboard'))
    return render_template('add_project.html')

@app.route('/task/<int:task_id>', methods=('GET', 'POST'))
def task_detail(task_id):
    conn = get_db_connection()
    if request.method == 'POST':
        
        if 'complete_task' in request.form:
            conn.execute('UPDATE tasks SET is_completed = 1 WHERE id = ?', (task_id,))
            should_log = True
        elif 'subtask_title' in request.form:
            subtask_title = request.form['subtask_title']
            conn.execute('INSERT INTO subtasks (task_id, title) VALUES (?, ?)', (task_id, subtask_title))
            should_log = True
        elif 'comment_content' in request.form:
            comment_content = request.form['comment_content']
            author = session.get('username') 
            conn.execute('INSERT INTO comments (task_id, content, author) VALUES (?, ?, ?)', (task_id, comment_content, author))
            should_log = True
        elif 'reassign_developer_id' in request.form:
            if session.get('role') in ['admin', 'manager']:
                new_dev_id = request.form['reassign_developer_id']
                conn.execute('UPDATE tasks SET developer_id = ? WHERE id = ?', (new_dev_id, task_id))
            should_log = False
        elif 'delete_subtask_id' in request.form:
            if session.get('role') in ['admin', 'manager']:
                subtask_id = request.form['delete_subtask_id']
                conn.execute('DELETE FROM subtasks WHERE id = ?', (subtask_id,))
            should_log = False
        elif 'complete_subtask_id' in request.form:
            if session.get('role') == 'developer':
                sub_id = request.form['complete_subtask_id']
                conn.execute('UPDATE subtasks SET is_completed = 1 WHERE id = ?', (sub_id,))
                should_log = True
        else:
            should_log = False
                
        conn.commit()
        conn.close()
        
        if should_log:
            log_activity(session['user_id'])
            
        return redirect(url_for('task_detail', task_id=task_id))

    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    subtasks = conn.execute('SELECT * FROM subtasks WHERE task_id = ?', (task_id,)).fetchall()
    comments = conn.execute('SELECT * FROM comments WHERE task_id = ? ORDER BY timestamp DESC', (task_id,)).fetchall()
    conn.close()
    
    return render_template('task_detail.html', task=task, subtasks=subtasks, comments=comments, role=session.get('role'), username=session.get('username'))

if __name__ == '__main__':
    app.run(debug=True)