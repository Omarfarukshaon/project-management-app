# 🚀 TaskFlow & Project Management Workspace

# 🚀 TaskFlow & Project Management Workspace

A secure, enterprise-grade, role-based Project Management web application built with **Flask** and **SQLite**, featuring granular access controls, task priority management, individual progress sliders, dashboard analytics, exportable CSV reports, and a **GitHub-style daily contribution heat map**.

---

## 🌟 Key Features

- **🔒 Role-Based Access Control (RBAC):**
  - **Admin:** Full global system visibility, project creation, user role management, and global activity monitoring.
  - **Managers:** Isolated project management where managers oversee their assigned projects, add tasks, and manage team members.
  - **Developers:** Focused access allowing developers to view assigned projects, update individual task progress via interactive sliders, and log work notes.

- **📊 Dashboard Analytics & Summary Metrics:**
  - Executive summary cards tracking total projects, assigned tasks, completed items, and overall success rate percentages.

- **🔥 GitHub-Style Contribution Heatmap:**
  - Tracks daily user workflow activity and productivity, visualized with green contribution level squares directly on the dashboard.

- **⚡ Task Priority & Filtering System:**
  - Assign priorities (*Low, Medium, High, Urgent*) with distinct color-coded badges.
  - Interactive task filtering toolbar in project workspaces to instantly filter tasks by status or priority.

- **⚠️ Overdue Task Warnings:**
  - Automatic date validation that flags missed deadlines with distinct red alert badges.

- **💬 Facebook-Style Collaboration:**
  - Clean comment streams with author tagging, timestamps, and smooth **"View more / View less"** expandable toggles for both projects and tasks.

- **📈 Role-Based CSV Reporting:**
  - Instantly download custom-tailored CSV summary reports depending on whether you are logged in as an Admin, Manager, or Developer.

- **👥 Profile & Security Management:**
  - Custom profile image avatar uploads, full name personalization, and secure password update workflows.

---

## 🛠️ Tech Stack

- **Backend:** Python, Flask, Werkzeug (Secure Filename / Utilities)
- **Database:** SQLite3 with parameterized queries and connection timeout safeguards
- **Frontend:** HTML5, Jinja2 Templating, CSS3 (Grid & Flexbox)
- **Icons & Fonts:** FontAwesome 6.4.0

---

## 📁 Project Structure

```text
Project management/
│
│
├── static/
│   ├── uploads/           # User-uploaded profile avatars
│   └── style.css          # Custom application styles and heatmap grid
│
├── templates/             # HTML Jinja2 templates
│   ├── add_project.html
│   ├── add_task.html
│   ├── admin_activities.html
│   ├── dashboard.html
│   ├── login.html
│   ├── manage_users.html
│   ├── profile.html
│   ├── project_detail.html
│   ├── projects_list.html
│   ├── task_detail.html
│   └── user_activity_detail.html
│
├── add_comments_db.py     # Database comment migration script
├── add_priority.py        # Task priority schema upgrade script
├── add_team.py            # Team management helper script
├── app.py                 # Main Flask application routes and logic
├── database.py            # Database initialization script
├── fix_comments.py        # Comment schema fix utility
├── fix_subtasks.py        # Subtask logic adjustment utility
├── phase1_db_update.py    # Phase 1 database migration script
├── project_manager.db     # SQLite database
├── README.md              # Project documentation
├── seed.py                # Database seeding script
├── setup_users.py         # Initial user creation utility
├── update_db.py           # General database updater
└── upgrade_profile.py     # Profile schema migration script

## 👨‍💻 Author

**Omar Faruk Shaon**
* GitHub: [@Omarfarukshaon](https://github.com/Omarfarukshaon)

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).