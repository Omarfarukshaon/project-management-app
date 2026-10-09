import sqlite3

def upgrade_priority():
    conn = sqlite3.connect('project_manager.db')
    try:
        conn.execute("ALTER TABLE tasks ADD COLUMN priority TEXT DEFAULT 'Medium'")
        print("Success! 'priority' column added to tasks table.")
    except sqlite3.OperationalError:
        print("Column 'priority' already exists.")
    conn.commit()
    conn.close()

if __name__ == '__main__':
    upgrade_priority()