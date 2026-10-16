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

# Weighted task checklists. Every set totals exactly 100 percentage points.
TASK_CRITERIA = {
    'use_case': [
        ('Identify all actors and external systems', 10),
        ('List the functional use cases from requirements', 15),
        ('Define the system boundary and scope', 10),
        ('Connect actors to the correct use cases', 15),
        ('Apply include, extend, and generalization relationships where appropriate', 15),
        ('Check that all important user goals are represented', 15),
        ('Use clear names, labels, and diagram notation', 10),
        ('Review the diagram against the requirements', 10),
    ],
    'er_diagram': [
        ('Identify all required entities', 10),
        ('Define attributes for each entity', 15),
        ('Choose primary keys and foreign keys', 15),
        ('Define relationships between entities', 15),
        ('Set correct cardinality and participation constraints', 15),
        ('Resolve many-to-many relationships using associative entities', 10),
        ('Review normalization and remove avoidable redundancy', 10),
        ('Validate the ER diagram against system requirements', 10),
    ],
    'sequence_diagram': [
        ('Select a clear use-case scenario and its main flow', 10),
        ('Identify actors, objects, and lifelines', 15),
        ('Add messages in the correct chronological order', 15),
        ('Show activation bars and object creation or termination where needed', 15),
        ('Represent alternative, optional, and repeated flows', 15),
        ('Include return messages and relevant conditions', 10),
        ('Keep interactions consistent with the use case and system design', 10),
        ('Review labels, notation, and diagram readability', 10),
    ],
    'database': [
        ('Identify data requirements and entities', 10),
        ('Define tables and appropriate columns', 10),
        ('Select primary keys and foreign keys', 15),
        ('Define data types, nullability, and default values', 15),
        ('Normalize tables to reduce duplication and anomalies', 15),
        ('Add unique, check, and other required constraints', 15),
        ('Create indexes for important query patterns', 10),
        ('Run sample queries and validate data integrity', 10),
    ],
    'system_design': [
        ('Translate requirements into a high-level system architecture', 10),
        ('Identify major modules and their responsibilities', 15),
        ('Define interfaces and communication between modules', 15),
        ('Design the application and data flow', 10),
        ('Choose suitable technologies and deployment structure', 10),
        ('Address security, performance, reliability, and scalability', 15),
        ('Prepare relevant component, deployment, or architecture diagrams', 15),
        ('Review the design for completeness and consistency', 10),
    ],
    'requirements': [
        ('Identify stakeholders and define the problem scope', 10),
        ('Gather and document stakeholder needs', 15),
        ('Identify and describe functional requirements', 15),
        ('Identify non-functional requirements', 15),
        ('Prepare use cases or user stories with acceptance conditions', 15),
        ('Prioritize requirements and identify constraints', 10),
        ('Check requirements for clarity, consistency, and testability', 10),
        ('Review and obtain stakeholder validation of the requirements document', 10),
    ],
    'implementation_testing': [
        ('Prepare the development environment and project structure', 10),
        ('Implement the assigned features and modules', 20),
        ('Follow the agreed architecture and coding standards', 15),
        ('Integrate the implemented modules', 15),
        ('Write and execute unit tests', 15),
        ('Execute integration and system tests', 10),
        ('Fix defects and retest affected functionality', 10),
        ('Update technical documentation and test evidence', 5),
    ],
    'quality_assurance': [
        ('Prepare a quality assurance plan and quality objectives', 10),
        ('Define applicable standards and acceptance criteria', 10),
        ('Review requirements, design, and code artifacts', 15),
        ('Verify functionality through planned tests', 15),
        ('Record, prioritize, and track defects', 15),
        ('Perform regression testing after fixes', 15),
        ('Check usability, reliability, and non-functional quality', 10),
        ('Prepare QA results and release-readiness sign-off', 10),
    ],
    'general': [
        ('Clarify the task scope and expected deliverable', 10),
        ('Review required inputs, dependencies, and constraints', 10),
        ('Prepare the approach or implementation plan', 15),
        ('Complete the main work for the task', 30),
        ('Validate the result against its acceptance criteria', 15),
        ('Resolve review findings and make necessary revisions', 10),
        ('Document and submit the completed deliverable', 10),
    ],
}


def criteria_category(task_title):
    title = (task_title or '').lower().replace('-', ' ').replace('_', ' ')
    if 'quality assurance' in title or 'quality control' in title or title.strip() == 'qa' or ' qa ' in f' {title} ':
        return 'quality_assurance'
    if any(word in title for word in ('requirement', 'srs', 'feasibility analysis', 'requirement analysis')):
        return 'requirements'
    if any(word in title for word in ('implementation', 'testing', 'test case', 'unit test', 'integration test')):
        return 'implementation_testing'
    if 'use case' in title:
        return 'use_case'
    if 'sequence' in title:
        return 'sequence_diagram'
    if 'er diagram' in title or 'entity relationship' in title:
        return 'er_diagram'
    if any(word in title for word in ('database', 'db schema', 'data schema')):
        return 'database'
    if any(word in title for word in ('system design', 'design the system', 'system architecture', 'architecture design')):
        return 'system_design'
    return 'general'


def _create_task_criteria(conn, task_id, task_title):
    existing = conn.execute('SELECT COUNT(*) FROM task_criteria WHERE task_id = ?', (task_id,)).fetchone()[0]
    if existing:
        return
    category = criteria_category(task_title)
    for position, (criterion_title, weight) in enumerate(TASK_CRITERIA[category], start=1):
        conn.execute('''
            INSERT INTO task_criteria (task_id, title, weight, position, category)
            VALUES (?, ?, ?, ?, ?)
        ''', (task_id, criterion_title, weight, position, category))


def _closest_criteria_subset(criteria_rows, target_progress):
    'Return criterion IDs whose total weight is closest to a legacy percentage.'
    possible = {0: []}
    for criterion_id, weight in criteria_rows:
        additions = {}
        for total, chosen in possible.items():
            new_total = total + int(weight)
            if new_total <= 100 and new_total not in possible and new_total not in additions:
                additions[new_total] = chosen + [criterion_id]
        possible.update(additions)
    best_total = min(possible, key=lambda total: (abs(total - int(target_progress or 0)), -total))
    return set(possible[best_total])


def _ensure_criterion_progress(conn, task_id, developer_id, initial_progress=None):
    criteria = conn.execute(
        'SELECT id, weight FROM task_criteria WHERE task_id = ? ORDER BY position, id',
        (task_id,)
    ).fetchall()
    if not criteria:
        return
    existing_count = conn.execute('''
        SELECT COUNT(*) FROM task_criterion_progress cp
        JOIN task_criteria tc ON tc.id = cp.criterion_id
        WHERE tc.task_id = ? AND cp.developer_id = ?
    ''', (task_id, developer_id)).fetchone()[0]
    if existing_count == 0 and initial_progress is not None:
        completed_ids = _closest_criteria_subset([(row[0], row[1]) for row in criteria], initial_progress)
    else:
        completed_ids = set()
    for criterion_id, _weight in criteria:
        conn.execute('''
            INSERT OR IGNORE INTO task_criterion_progress (criterion_id, developer_id, is_completed)
            VALUES (?, ?, ?)
        ''', (criterion_id, developer_id, 1 if criterion_id in completed_ids else 0))


def _recalculate_task_progress(conn, task_id, developer_id=None):
    if developer_id is not None:
        progress_row = conn.execute('''
            SELECT COALESCE(SUM(CASE WHEN cp.is_completed = 1 THEN tc.weight ELSE 0 END), 0) AS progress
            FROM task_criteria tc
            LEFT JOIN task_criterion_progress cp
              ON cp.criterion_id = tc.id AND cp.developer_id = ?
            WHERE tc.task_id = ?
        ''', (developer_id, task_id)).fetchone()
        conn.execute(
            'UPDATE task_assignments SET progress = ? WHERE task_id = ? AND developer_id = ?',
            (int(progress_row[0] or 0), task_id, developer_id)
        )
    average = conn.execute(
        'SELECT AVG(progress) FROM task_assignments WHERE task_id = ?', (task_id,)
    ).fetchone()[0]
    if average is None:
        global_progress = conn.execute('''
            SELECT COALESCE(SUM(CASE WHEN is_completed = 1 THEN weight ELSE 0 END), 0)
            FROM task_criteria WHERE task_id = ?
        ''', (task_id,)).fetchone()[0]
        conn.execute('UPDATE tasks SET progress = ?, is_completed = ? WHERE id = ?',
                     (int(global_progress or 0), 1 if global_progress == 100 else 0, task_id))
        return
    overall = int(round(average))
    conn.execute(
        'UPDATE tasks SET progress = ?, is_completed = ? WHERE id = ?',
        (overall, 1 if overall == 100 else 0, task_id)
    )

# Automatically upgrades database schema to support per-developer task progress tracking & priority
def upgrade_database_schema():
    conn = sqlite3.connect('project_manager.db', timeout=10.0)
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

    # Keep the existing project manager field intact, while allowing additional
    # managers to be assigned to a project by an administrator.
    conn.execute('''
        CREATE TABLE IF NOT EXISTS project_manager_teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            manager_id INTEGER NOT NULL,
            UNIQUE(project_id, manager_id),
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (manager_id) REFERENCES users(id)
        )
    ''')
    conn.execute('''
        INSERT OR IGNORE INTO project_manager_teams (project_id, manager_id)
        SELECT p.id, p.manager_id
        FROM projects p JOIN users u ON u.id = p.manager_id
        WHERE u.role = 'manager'
    ''')

    # Criteria are attached to a task; completion is tracked independently for
    # every assigned developer to preserve the existing individual progress model.
    conn.execute('''
        CREATE TABLE IF NOT EXISTS task_criteria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            weight INTEGER NOT NULL,
            position INTEGER NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            is_completed INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    try:
        conn.execute('ALTER TABLE task_criteria ADD COLUMN is_completed INTEGER NOT NULL DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute('ALTER TABLE tasks ADD COLUMN criteria_initialized INTEGER NOT NULL DEFAULT 0')
    except sqlite3.OperationalError:
        pass

    conn.execute('''
        CREATE TABLE IF NOT EXISTS task_criterion_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            criterion_id INTEGER NOT NULL,
            developer_id INTEGER NOT NULL,
            is_completed INTEGER NOT NULL DEFAULT 0,
            UNIQUE(criterion_id, developer_id),
            FOREIGN KEY (criterion_id) REFERENCES task_criteria(id),
            FOREIGN KEY (developer_id) REFERENCES users(id)
        )
    ''')
    # Repair older installations where the table existed without the unique
    # constraint. Keep one row for each criterion/developer pair, then enforce it.
    conn.execute('''
        DELETE FROM task_criterion_progress
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM task_criterion_progress
            GROUP BY criterion_id, developer_id
        )
    ''')
    conn.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_task_criterion_developer
        ON task_criterion_progress (criterion_id, developer_id)
    ''')

    # Bring older single-developer task assignments into the current multi-assignee
    # table, but only when the referenced account is an actual developer.
    conn.execute('''
        INSERT INTO task_assignments (task_id, developer_id, progress)
        SELECT t.id, t.developer_id, COALESCE(t.progress, 0)
        FROM tasks t JOIN users u ON u.id = t.developer_id AND u.role = 'developer'
        WHERE t.developer_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM task_assignments ta
              WHERE ta.task_id = t.id AND ta.developer_id = t.developer_id
          )
    ''')

    tasks = conn.execute('SELECT id, title, COALESCE(progress, 0), COALESCE(criteria_initialized, 0) FROM tasks ORDER BY id').fetchall()
    for task_id, title, _legacy_progress, _initialized in tasks:
        _create_task_criteria(conn, task_id, title)

    assignments = conn.execute(
        'SELECT task_id, developer_id, COALESCE(progress, 0) FROM task_assignments'
    ).fetchall()
    for task_id, developer_id, progress in assignments:
        _ensure_criterion_progress(conn, task_id, developer_id, progress)
        _recalculate_task_progress(conn, task_id, developer_id)

    # For older tasks with no assigned developer, provide an editable task-wide
    # checklist so every task can still be completed and measured by its criteria.
    for task_id, _title, legacy_progress, initialized in tasks:
        assignment_count = conn.execute(
            'SELECT COUNT(*) FROM task_assignments WHERE task_id = ?', (task_id,)
        ).fetchone()[0]
        if assignment_count == 0 and not initialized:
            criteria_rows = conn.execute(
                'SELECT id, weight FROM task_criteria WHERE task_id = ? ORDER BY position, id',
                (task_id,)
            ).fetchall()
            completed_ids = _closest_criteria_subset([(row[0], row[1]) for row in criteria_rows], legacy_progress)
            for criterion_id, _weight in criteria_rows:
                conn.execute('UPDATE task_criteria SET is_completed = ? WHERE id = ?',
                             (1 if criterion_id in completed_ids else 0, criterion_id))
            _recalculate_task_progress(conn, task_id)
        conn.execute('UPDATE tasks SET criteria_initialized = 1 WHERE id = ?', (task_id,))

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
        projects = conn.execute('''
            SELECT DISTINCT p.* FROM projects p
            LEFT JOIN project_manager_teams pmt ON pmt.project_id = p.id
            WHERE p.manager_id = ? OR pmt.manager_id = ?
            ORDER BY p.id DESC LIMIT 7
        ''', (user_id, user_id)).fetchall()
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
    return render_template('dashboard.html', projects=projects, role=user_role, user=current_user,
                           dashboard_title=dashboard_title, days=days)


@app.route('/projects')
def project_list():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    user_role = session.get('role')
    user_id = session.get('user_id')
    search_query = request.args.get('q', '').strip()
    search_pattern = '%' + search_query + '%'

    if user_role == 'admin':
        if search_query:
            projects = conn.execute('SELECT * FROM projects WHERE title LIKE ? ORDER BY id DESC', (search_pattern,)).fetchall()
        else:
            projects = conn.execute('SELECT * FROM projects ORDER BY id DESC').fetchall()
    elif user_role == 'manager':
        base_sql = '''
            SELECT DISTINCT p.* FROM projects p
            LEFT JOIN project_manager_teams pmt ON pmt.project_id = p.id
            WHERE (p.manager_id = ? OR pmt.manager_id = ?)
        '''
        if search_query:
            projects = conn.execute(base_sql + ' AND p.title LIKE ? ORDER BY p.id DESC',
                                    (user_id, user_id, search_pattern)).fetchall()
        else:
            projects = conn.execute(base_sql + ' ORDER BY p.id DESC', (user_id, user_id)).fetchall()
    else:
        if search_query:
            projects = conn.execute('''
                SELECT DISTINCT projects.* FROM projects
                JOIN tasks ON projects.id = tasks.project_id
                JOIN task_assignments ON tasks.id = task_assignments.task_id
                WHERE task_assignments.developer_id = ? AND projects.title LIKE ?
                ORDER BY projects.id DESC
            ''', (user_id, search_pattern)).fetchall()
        else:
            projects = conn.execute('''
                SELECT DISTINCT projects.* FROM projects
                JOIN tasks ON projects.id = tasks.project_id
                JOIN task_assignments ON tasks.id = task_assignments.task_id
                WHERE task_assignments.developer_id = ? ORDER BY projects.id DESC
            ''', (user_id,)).fetchall()

    conn.close()
    # The supplied frontend file is named project_list.html.
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
    project = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        conn.close()
        return "Project not found.", 404

    is_project_manager = conn.execute('''
        SELECT 1 FROM project_manager_teams WHERE project_id = ? AND manager_id = ?
    ''', (project_id, user_id)).fetchone()
    if user_role == 'manager' and project['manager_id'] != user_id and not is_project_manager:
        conn.close()
        return "Access Denied: You are not assigned to manage this project.", 403
    if user_role == 'developer':
        assigned_check = conn.execute(
            'SELECT 1 FROM project_teams WHERE project_id = ? AND developer_id = ?',
            (project_id, user_id)
        ).fetchone()
        if not assigned_check:
            fallback = conn.execute('''
                SELECT 1 FROM tasks t JOIN task_assignments ta ON t.id = ta.task_id
                WHERE t.project_id = ? AND ta.developer_id = ?
            ''', (project_id, user_id)).fetchone()
            if not fallback:
                conn.close()
                return "Access Denied: You are not assigned to this project.", 403

    if request.method == 'POST':
        if 'project_comment' in request.form:
            content = request.form['project_comment'].strip()
            if content:
                conn.execute(
                    'INSERT INTO project_comments (project_id, author, content) VALUES (?, ?, ?)',
                    (project_id, session.get('username'), content)
                )
        elif 'add_developer' in request.form and user_role in ['admin', 'manager']:
            new_dev_id = request.form.get('new_developer_id', type=int)
            valid_dev = conn.execute("SELECT 1 FROM users WHERE id = ? AND role = 'developer'", (new_dev_id,)).fetchone()
            if valid_dev:
                conn.execute('INSERT OR IGNORE INTO project_teams (project_id, developer_id) VALUES (?, ?)',
                             (project_id, new_dev_id))
        elif 'remove_developer_id' in request.form and user_role in ['admin', 'manager']:
            remove_dev_id = request.form.get('remove_developer_id', type=int)
            conn.execute('DELETE FROM project_teams WHERE project_id = ? AND developer_id = ?',
                         (project_id, remove_dev_id))
        elif 'add_manager' in request.form and user_role == 'admin':
            new_manager_id = request.form.get('new_manager_id', type=int)
            valid_manager = conn.execute("SELECT 1 FROM users WHERE id = ? AND role = 'manager'", (new_manager_id,)).fetchone()
            if valid_manager:
                conn.execute('INSERT OR IGNORE INTO project_manager_teams (project_id, manager_id) VALUES (?, ?)',
                             (project_id, new_manager_id))
                primary_is_manager = conn.execute(
                    "SELECT 1 FROM users WHERE id = ? AND role = 'manager'", (project['manager_id'],)
                ).fetchone()
                if not primary_is_manager:
                    conn.execute('UPDATE projects SET manager_id = ? WHERE id = ?', (new_manager_id, project_id))
        elif 'remove_manager_id' in request.form and user_role == 'admin':
            remove_manager_id = request.form.get('remove_manager_id', type=int)
            conn.execute('DELETE FROM project_manager_teams WHERE project_id = ? AND manager_id = ?',
                         (project_id, remove_manager_id))
            if project['manager_id'] == remove_manager_id:
                replacement = conn.execute('''
                    SELECT manager_id FROM project_manager_teams
                    WHERE project_id = ? ORDER BY id LIMIT 1
                ''', (project_id,)).fetchone()
                conn.execute('UPDATE projects SET manager_id = ? WHERE id = ?',
                             (replacement['manager_id'] if replacement else None, project_id))
        conn.commit()
        conn.close()
        return redirect(url_for('project_detail', project_id=project_id))

    # Keep project-team membership in sync with all currently assigned developers.
    conn.execute('''
        INSERT OR IGNORE INTO project_teams (project_id, developer_id)
        SELECT DISTINCT t.project_id, ta.developer_id
        FROM tasks t JOIN task_assignments ta ON t.id = ta.task_id
        JOIN users u ON u.id = ta.developer_id AND u.role = 'developer'
        WHERE t.project_id = ?
    ''', (project_id,))
    conn.commit()

    if user_role in ['admin', 'manager']:
        tasks = conn.execute('SELECT * FROM tasks WHERE project_id = ? ORDER BY id DESC', (project_id,)).fetchall()
    else:
        tasks = conn.execute('''
            SELECT DISTINCT t.* FROM tasks t
            JOIN task_assignments ta ON t.id = ta.task_id
            WHERE t.project_id = ? AND ta.developer_id = ? ORDER BY t.id DESC
        ''', (project_id, user_id)).fetchall()

    task_progress_list = []
    tasks_with_progress = []
    for t in tasks:
        avg_prog = conn.execute(
            'SELECT AVG(progress) FROM task_assignments WHERE task_id = ?', (t['id'],)
        ).fetchone()[0]
        t_prog = int(round(avg_prog)) if avg_prog is not None else t['progress']
        task_progress_list.append(t_prog)
        t_dict = dict(t)
        t_dict['progress'] = t_prog
        tasks_with_progress.append(t_dict)

    progress_percentage = int(round(sum(task_progress_list) / len(task_progress_list))) if task_progress_list else 0
    manager_details = conn.execute(
        "SELECT id, username, full_name, profile_image, role FROM users WHERE id = ? AND role = 'manager'",
        (project['manager_id'],)
    ).fetchone() if project['manager_id'] else None

    manager_members = conn.execute('''
        SELECT u.id, u.username, u.full_name, u.profile_image, u.role,
               CASE WHEN p.manager_id = u.id THEN 1 ELSE 0 END AS is_primary
        FROM project_manager_teams pmt
        JOIN users u ON u.id = pmt.manager_id
        JOIN projects p ON p.id = pmt.project_id
        WHERE pmt.project_id = ? AND u.role = 'manager'
        ORDER BY is_primary DESC, u.full_name, u.username
    ''', (project_id,)).fetchall()

    team_members = conn.execute('''
    SELECT
        u.id,
        u.username,
        u.full_name,
        u.profile_image,
        u.role,

        (
            SELECT COUNT(*)
            FROM task_assignments ta
            JOIN tasks t ON t.id = ta.task_id
            WHERE ta.developer_id = u.id
              AND t.project_id = pt.project_id
        ) AS total_tasks,

        (
            SELECT COUNT(*)
            FROM task_assignments ta
            JOIN tasks t ON t.id = ta.task_id
            WHERE ta.developer_id = u.id
              AND t.project_id = pt.project_id
              AND ta.progress = 100
        ) AS completed_tasks

    FROM project_teams pt

    JOIN users u
        ON u.id = pt.developer_id
        AND u.role = 'developer'

    WHERE pt.project_id = ?

    GROUP BY u.id

    ORDER BY u.full_name, u.username

''', (project_id,)).fetchall()

    available_devs = conn.execute('''
        SELECT id, username, full_name FROM users
        WHERE role = 'developer' AND id NOT IN (
            SELECT developer_id FROM project_teams WHERE project_id = ?
        ) ORDER BY full_name, username
    ''', (project_id,)).fetchall()
    available_managers = []
    if user_role == 'admin':
        available_managers = conn.execute('''
            SELECT id, username, full_name FROM users
            WHERE role = 'manager' AND id NOT IN (
                SELECT manager_id FROM project_manager_teams WHERE project_id = ?
            ) ORDER BY full_name, username
        ''', (project_id,)).fetchall()

    project_comments = conn.execute(
        'SELECT * FROM project_comments WHERE project_id = ? ORDER BY timestamp DESC', (project_id,)
    ).fetchall()
    conn.close()
    today = date.today().strftime('%Y-%m-%d')

    return render_template('project_detail.html', project=project, tasks=tasks_with_progress, today=today,
                           role=user_role, progress_percentage=progress_percentage, team_members=team_members,
                           manager_details=manager_details, manager_members=manager_members,
                           available_devs=available_devs, available_managers=available_managers,
                           project_comments=project_comments)

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
        valid_manager = conn.execute("SELECT 1 FROM users WHERE id = ? AND role = 'manager'", (manager_id,)).fetchone()
        if not valid_manager:
            conn.close()
            return "Please select a valid project manager.", 400
        cursor.execute('INSERT INTO projects (title, manager_id, deadline) VALUES (?, ?, ?)',
                       (project_title, manager_id, project_deadline))
        project_id = cursor.lastrowid
        conn.execute('INSERT OR IGNORE INTO project_manager_teams (project_id, manager_id) VALUES (?, ?)',
                     (project_id, manager_id))
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

    project = conn.execute(
        'SELECT * FROM projects WHERE id = ?', (project_id,)
    ).fetchone()

    if not project:
        conn.close()
        return "Project not found.", 404

    if session.get('role') == 'manager':

        membership = conn.execute('''
            SELECT 1 FROM project_manager_teams
            WHERE project_id = ? AND manager_id = ?
        ''', (project_id, session.get('user_id'))).fetchone()

        if project['manager_id'] != session.get('user_id') and not membership:
            conn.close()
            return "Access Denied.", 403

    task_options = {
        'Use Case Diagram': 'use_case',
        'ER Diagram': 'er_diagram',
        'Sequence Diagram': 'sequence_diagram',
        'Database Design': 'database',
        'System Design': 'system_design',
        'Requirements Analysis': 'requirements',
        'Implementation & Testing': 'implementation_testing',
        'Quality Assurance': 'quality_assurance',
        'General Task': 'general'
    }

    if request.method == 'POST':

        task_title = request.form.get('task_title', '').strip()
        task_deadline = request.form.get('task_deadline', '').strip()
        priority = request.form.get('priority', 'Medium')

        if task_title not in task_options:
            conn.close()
            return "Please select a valid task.", 400

        if not task_deadline:
            conn.close()
            return "Please select a task deadline.", 400

        if priority not in ['Low', 'Medium', 'High', 'Urgent']:
            conn.close()
            return "Invalid task priority.", 400

        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO tasks
            (project_id, title, deadline, is_completed, progress, priority)
            VALUES (?, ?, ?, 0, 0, ?)
        ''', (
            project_id,
            task_title,
            task_deadline,
            priority
        ))

        task_id = cursor.lastrowid

        # Automatically generate the checklist for this task.
        _create_task_criteria(conn, task_id, task_title)

        conn.execute('''
            UPDATE tasks
            SET criteria_initialized = 1
            WHERE id = ?
        ''', (task_id,))

        # Automatically assign all existing project developers.
        project_developers = conn.execute('''
            SELECT developer_id
            FROM project_teams
            WHERE project_id = ?
        ''', (project_id,)).fetchall()

        for row in project_developers:

            dev_id = row['developer_id']

            valid_dev = conn.execute('''
                SELECT 1 FROM users
                WHERE id = ? AND role = 'developer'
            ''', (dev_id,)).fetchone()

            if not valid_dev:
                continue

            conn.execute('''
                INSERT OR IGNORE INTO task_assignments
                (task_id, developer_id, progress)
                VALUES (?, ?, 0)
            ''', (task_id, dev_id))

            # Give each developer an independent checklist.
            _ensure_criterion_progress(
                conn, task_id, dev_id, 0
            )

            _recalculate_task_progress(
                conn, task_id, dev_id
            )

        conn.commit()
        conn.close()

        log_activity(session['user_id'])

        return redirect(
            url_for('project_detail', project_id=project_id)
        )

    conn.close()

    return render_template(
        'add_task.html',
        project=project,
        task_options=task_options
    )
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
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not task:
        conn.close()
        return "Task not found", 404

    try:
        task_deadline = date.fromisoformat(str(task['deadline'])[:10])
        deadline_passed = task_deadline < date.today()
    except (TypeError, ValueError):
        deadline_passed = False

    user_id = session.get('user_id')
    user_role = session.get('role')
    project = conn.execute('SELECT * FROM projects WHERE id = ?', (task['project_id'],)).fetchone()
    if user_role == 'manager':
        manager_membership = conn.execute('''
            SELECT 1 FROM project_manager_teams WHERE project_id = ? AND manager_id = ?
        ''', (task['project_id'], user_id)).fetchone()
        if not manager_membership and project['manager_id'] != user_id:
            conn.close()
            return "Access Denied.", 403
    elif user_role == 'developer':
        own_assignment = conn.execute(
            'SELECT 1 FROM task_assignments WHERE task_id = ? AND developer_id = ?', (task_id, user_id)
        ).fetchone()
        if not own_assignment:
            conn.close()
            return "Access Denied: This task is not assigned to you.", 403
    elif user_role != 'admin':
        conn.close()
        return "Access Denied.", 403

    if request.method == 'POST':
        locked_actions = ('toggle_criterion', 'update_progress', 'add_assignee_id', 'remove_assignee_id')
        if deadline_passed and any(action in request.form for action in locked_actions):
            conn.close()
            return ("This task's deadline has passed. Checklist, progress, and assignment changes are locked.", 403)

        should_log = False
        if 'toggle_criterion' in request.form:
            criterion_id = request.form.get('criterion_id', type=int)
            target_developer_id = user_id if user_role == 'developer' else request.form.get('developer_id', type=int)
            criterion = conn.execute('''
                SELECT id FROM task_criteria WHERE id = ? AND task_id = ?
            ''', (criterion_id, task_id)).fetchone()
            is_completed = 1 if 'completed' in request.form else 0
            if criterion and target_developer_id is None and user_role in ['admin', 'manager']:
                assignment_count = conn.execute(
                    'SELECT COUNT(*) FROM task_assignments WHERE task_id = ?', (task_id,)
                ).fetchone()[0]
                if assignment_count == 0:
                    conn.execute('UPDATE task_criteria SET is_completed = ? WHERE id = ? AND task_id = ?',
                                 (is_completed, criterion_id, task_id))
                    _recalculate_task_progress(conn, task_id)
                    should_log = True
            else:
                assignment = conn.execute('''
                    SELECT 1 FROM task_assignments WHERE task_id = ? AND developer_id = ?
                ''', (task_id, target_developer_id)).fetchone()
                can_update_target = user_role in ['admin', 'manager'] or target_developer_id == user_id
                if criterion and assignment and can_update_target:
                    _ensure_criterion_progress(conn, task_id, target_developer_id)
                    conn.execute('''
                        UPDATE task_criterion_progress SET is_completed = ?
                        WHERE criterion_id = ? AND developer_id = ?
                    ''', (is_completed, criterion_id, target_developer_id))
                    _recalculate_task_progress(conn, task_id, target_developer_id)
                    should_log = True
        elif 'add_work_log' in request.form:
            progress_note = request.form.get('progress_note', '').strip()
            if progress_note:
                author = session.get('username')
                conn.execute('INSERT INTO comments (task_id, content, author) VALUES (?, ?, ?)',
                             (task_id, f"[Work Log]: {progress_note}", author))
                should_log = True
        # Backward compatibility for an old percentage-slider form. A manager/admin
        # must target one developer; never apply one submitted percentage to everyone.
        elif 'update_progress' in request.form:
            try:
                new_progress = max(0, min(100, int(request.form.get('progress_value', 0))))
            except (TypeError, ValueError):
                new_progress = 0

            target_developer_id = user_id if user_role == 'developer' else request.form.get('developer_id', type=int)
            assignment = conn.execute('''
                SELECT 1 FROM task_assignments WHERE task_id = ? AND developer_id = ?
            ''', (task_id, target_developer_id)).fetchone() if target_developer_id is not None else None

            if assignment and (user_role in ['admin', 'manager'] or target_developer_id == user_id):
                progress_note = request.form.get('progress_note', '').strip()
                criteria_rows = conn.execute(
                    'SELECT id, weight FROM task_criteria WHERE task_id = ? ORDER BY position, id', (task_id,)
                ).fetchall()
                selected = _closest_criteria_subset([(row[0], row[1]) for row in criteria_rows], new_progress)
                _ensure_criterion_progress(conn, task_id, target_developer_id)
                for criterion_id, _weight in criteria_rows:
                    conn.execute('''
                        UPDATE task_criterion_progress SET is_completed = ?
                        WHERE criterion_id = ? AND developer_id = ?
                    ''', (1 if criterion_id in selected else 0, criterion_id, target_developer_id))
                _recalculate_task_progress(conn, task_id, target_developer_id)
                if progress_note:
                    author = session.get('username')
                    conn.execute('INSERT INTO comments (task_id, content, author) VALUES (?, ?, ?)',
                                 (task_id, f"[Progress Update -> requested {new_progress}% by {author}]: {progress_note}", author))
                should_log = True
        elif 'comment_content' in request.form:
            comment_content = request.form['comment_content'].strip()
            if comment_content:
                conn.execute('INSERT INTO comments (task_id, content, author) VALUES (?, ?, ?)',
                             (task_id, comment_content, session.get('username')))
                should_log = True
        elif 'add_assignee_id' in request.form and user_role in ['admin', 'manager']:
            new_dev_id = request.form.get('add_assignee_id', type=int)
            valid_dev = conn.execute("SELECT 1 FROM users WHERE id = ? AND role = 'developer'", (new_dev_id,)).fetchone()
            if valid_dev:
                conn.execute('INSERT OR IGNORE INTO task_assignments (task_id, developer_id, progress) VALUES (?, ?, 0)',
                             (task_id, new_dev_id))
                # Every developer starts with their own independent checklist.
                # Do not copy task-wide or another developer's checked criteria.
                _ensure_criterion_progress(conn, task_id, new_dev_id, 0)
                _recalculate_task_progress(conn, task_id, new_dev_id)
                conn.execute('INSERT OR IGNORE INTO project_teams (project_id, developer_id) VALUES (?, ?)',
                             (task['project_id'], new_dev_id))
        elif 'remove_assignee_id' in request.form and user_role in ['admin', 'manager']:
            remove_dev_id = request.form.get('remove_assignee_id', type=int)
            conn.execute('DELETE FROM task_criterion_progress WHERE developer_id = ? AND criterion_id IN '
                         '(SELECT id FROM task_criteria WHERE task_id = ?)', (remove_dev_id, task_id))
            conn.execute('DELETE FROM task_assignments WHERE task_id = ? AND developer_id = ?',
                         (task_id, remove_dev_id))
            _recalculate_task_progress(conn, task_id)

        conn.commit()
        conn.close()
        if should_log:
            log_activity(user_id)
        redirect_args = {'task_id': task_id}
        selected_after_post = request.form.get('developer_id', type=int)
        if selected_after_post is None:
            selected_after_post = request.args.get('developer_id', type=int)
        if selected_after_post is not None:
            redirect_args['developer_id'] = selected_after_post
        return redirect(url_for('task_detail', **redirect_args))

    comments = conn.execute('SELECT * FROM comments WHERE task_id = ? ORDER BY timestamp DESC', (task_id,)).fetchall()
    assigned_devs = conn.execute('''
        SELECT u.id, u.username, u.full_name, u.profile_image, ta.progress
        FROM users u JOIN task_assignments ta ON u.id = ta.developer_id
        WHERE ta.task_id = ? ORDER BY u.full_name, u.username
    ''', (task_id,)).fetchall()

    selected_developer_id = request.args.get('developer_id', type=int)
    assigned_ids = {dev['id'] for dev in assigned_devs}
    if user_role == 'developer':
        selected_developer_id = user_id
    elif selected_developer_id not in assigned_ids:
        selected_developer_id = None

    criterion_groups = []
    for dev in assigned_devs:
        if selected_developer_id is None or dev['id'] != selected_developer_id:
            continue
        _ensure_criterion_progress(conn, task_id, dev['id'])
        criteria = conn.execute('''
            SELECT tc.id, tc.title, tc.weight, tc.position,
                   COALESCE(cp.is_completed, 0) AS is_completed
            FROM task_criteria tc
            LEFT JOIN task_criterion_progress cp
              ON cp.criterion_id = tc.id AND cp.developer_id = ?
            WHERE tc.task_id = ?
            ORDER BY tc.position, tc.id
        ''', (dev['id'], task_id)).fetchall()
        criterion_groups.append({'developer': dev, 'criteria': criteria})

    my_progress = 0
    if user_role == 'developer':
        my_row = conn.execute(
            'SELECT progress FROM task_assignments WHERE task_id = ? AND developer_id = ?', (task_id, user_id)
        ).fetchone()
        if my_row:
            my_progress = my_row['progress']
    else:
        my_progress = task['progress']

    available_devs = conn.execute('''
        SELECT id, username, full_name FROM users
        WHERE role = 'developer' AND id NOT IN (
            SELECT developer_id FROM task_assignments WHERE task_id = ?
        ) ORDER BY full_name, username
    ''', (task_id,)).fetchall()
    criteria_total = conn.execute(
        'SELECT COALESCE(SUM(weight), 0) FROM task_criteria WHERE task_id = ?', (task_id,)
    ).fetchone()[0]
    unassigned_criteria = []
    if user_role in ['admin', 'manager'] and not assigned_devs:
        unassigned_criteria = conn.execute('''
            SELECT id, title, weight, position, is_completed
            FROM task_criteria WHERE task_id = ? ORDER BY position, id
        ''', (task_id,)).fetchall()
    today = date.today().strftime('%Y-%m-%d')
    conn.close()

    return render_template('task_detail.html', task=task, comments=comments,
                           assigned_devs=assigned_devs, available_devs=available_devs,
                           criterion_groups=criterion_groups, unassigned_criteria=unassigned_criteria,
                           criteria_total=criteria_total, role=user_role,
                           username=session.get('username'), my_progress=my_progress, today=today,
                           deadline_passed=deadline_passed, selected_developer_id=selected_developer_id)

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
        projects = conn.execute('''SELECT DISTINCT p.* FROM projects p LEFT JOIN project_manager_teams pmt ON pmt.project_id = p.id WHERE p.manager_id = ? OR pmt.manager_id = ?''', (user_id, user_id)).fetchall()
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