import sqlite3

def update_db():
    conn = sqlite3.connect('project_manager.db')
    try:
        # Add the is_completed column, defaulting to 0 (Not Completed)
        conn.execute("ALTER TABLE subtasks ADD COLUMN is_completed INTEGER DEFAULT 0")
        print("Success! 'is_completed' column added to the subtasks table.")
    except sqlite3.OperationalError:
        print("The column already exists!")
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    update_db()