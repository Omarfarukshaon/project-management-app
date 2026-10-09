import sqlite3

def update_database_for_phase1():
    conn = sqlite3.connect('project_manager.db')
    cursor = conn.cursor()

    # 1. Project-Level Comments Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS project_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            author TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects (id)
        )
    ''')

    # 2. Task Assignments Table (For assigning multiple developers to a task)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            developer_id INTEGER,
            FOREIGN KEY (task_id) REFERENCES tasks (id),
            FOREIGN KEY (developer_id) REFERENCES users (id)
        )
    ''')

    # 3. Project Teams Table (To pool developers assigned to a specific project)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS project_teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            developer_id INTEGER,
            FOREIGN KEY (project_id) REFERENCES projects (id),
            FOREIGN KEY (developer_id) REFERENCES users (id)
        )
    ''')

    conn.commit()
    conn.close()
    print("Phase 1 Database Update Successful! New tables added.")

if __name__ == '__main__':
    update_database_for_phase1()