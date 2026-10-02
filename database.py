import sqlite3

def init_db():
    # Connect to a database file (this will create 'project_manager.db' if it doesn't exist)
    conn = sqlite3.connect('project_manager.db')
    cursor = conn.cursor()

    # Create the Projects table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            manager_id INTEGER,
            deadline DATE,
            status TEXT DEFAULT 'Ongoing'
        )
    ''')

    # Create the Tasks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            developer_id INTEGER,
            title TEXT NOT NULL,
            deadline DATE,
            is_completed BOOLEAN DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES projects (id)
        )
    ''')

    # Commit changes and close the connection
    conn.commit()
    conn.close()
    print("Database and tables created successfully!")

if __name__ == '__main__':
    init_db()