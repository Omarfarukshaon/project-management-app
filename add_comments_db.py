import sqlite3

def add_comments_table():
    conn = sqlite3.connect('project_manager.db')
    
    # Create the Comments table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Comments table added successfully!")

if __name__ == '__main__':
    add_comments_table()