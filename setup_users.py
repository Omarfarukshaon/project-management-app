import sqlite3

def setup_users():
    conn = sqlite3.connect('project_manager.db')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    
    try:
        conn.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'admin123', 'admin')")
        conn.execute("INSERT INTO users (username, password, role) VALUES ('dev1', 'dev123', 'developer')")
    except sqlite3.IntegrityError:
        pass 
        
    conn.commit()
    conn.close()
    print("Users table created and dummy accounts added!")

if __name__ == '__main__':
    setup_users()