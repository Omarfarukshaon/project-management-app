import sqlite3

def add_team_members():
    conn = sqlite3.connect('project_manager.db')
    
    # List of new users to add (username, password, role, full_name)
    new_users = [
        ('manager1', 'mgr123', 'manager', 'Alice Manager'),
        ('manager2', 'mgr123', 'manager', 'Bob Manager'),
        ('dev3', 'dev123', 'developer', 'Charlie Developer'),
        ('dev4', 'dev123', 'developer', 'Diana Developer')
    ]
    
    for username, password, role, full_name in new_users:
        try:
            conn.execute(
                "INSERT INTO users (username, password, role, full_name, profile_image) VALUES (?, ?, ?, ?, 'default.png')",
                (username, password, role, full_name)
            )
            print(f"Successfully added {username} as a {role}!")
        except sqlite3.IntegrityError:
            print(f"User '{username}' already exists in the database.")
            
    conn.commit()
    conn.close()

if __name__ == '__main__':
    add_team_members()