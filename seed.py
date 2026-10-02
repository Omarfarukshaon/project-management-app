import sqlite3

def seed_data():
    conn = sqlite3.connect('project_manager.db')
    cursor = conn.cursor()

    # Insert a dummy project
    cursor.execute("INSERT INTO projects (title, manager_id, deadline) VALUES ('Software Engineering Project', 1, '2026-12-31')")
    
    # Insert Task 1: Completed (Should show as Green)
    cursor.execute("INSERT INTO tasks (project_id, developer_id, title, deadline, is_completed) VALUES (1, 101, 'Design Database', '2026-09-10', 1)")
    
    # Insert Task 2: Overdue and not completed (Should show as Red)
    cursor.execute("INSERT INTO tasks (project_id, developer_id, title, deadline, is_completed) VALUES (1, 102, 'Build Frontend', '2026-09-01', 0)")

    conn.commit()
    conn.close()
    print("Dummy data added!")

if __name__ == '__main__':
    seed_data()