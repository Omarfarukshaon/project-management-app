import sqlite3

def add_tables():
    conn = sqlite3.connect('project_manager.db')
    
    # Create the Subtasks table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS subtasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            title TEXT NOT NULL,
            is_completed BOOLEAN DEFAULT 0,
            FOREIGN KEY (task_id) REFERENCES tasks (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Subtasks table added successfully!")

if __name__ == '__main__':
    add_tables()