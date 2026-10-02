import sqlite3

def upgrade_db():
    conn = sqlite3.connect('project_manager.db')
    
    # 1. Add profile columns to users table
    try:
        conn.execute("ALTER TABLE users ADD COLUMN full_name TEXT DEFAULT ''")
        conn.execute("ALTER TABLE users ADD COLUMN profile_image TEXT DEFAULT 'default.png'")
        print("Profile columns added to users table.")
    except sqlite3.OperationalError:
        print("Profile columns already exist.")
        
    # 2. Create an Activities table for the GitHub-style graph
    conn.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            user_id INTEGER,
            date TEXT,
            count INTEGER DEFAULT 1,
            PRIMARY KEY (user_id, date)
        )
    ''')
    print("Activities table created for the progress graph!")
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    upgrade_db()