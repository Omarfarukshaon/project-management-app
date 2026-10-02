import sqlite3

def update_db():
    conn = sqlite3.connect('project_manager.db')
    try:
        # Add the author column, defaulting to 'Unknown' for older comments
        conn.execute("ALTER TABLE comments ADD COLUMN author TEXT DEFAULT 'Unknown'")
        print("Success! Author column added to the comments table.")
    except sqlite3.OperationalError:
        print("The author column already exists!")
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    update_db()