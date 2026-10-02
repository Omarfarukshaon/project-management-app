# 🚀 TaskFlow & Project Management Workspace

A secure, role-based Project Management web application built with **Flask** and **SQLite**, featuring granular access controls, interactive subtask tracking, user profile customization, and a **GitHub-style daily contribution heat map**.

---

## 🌟 Key Features

*   **🔒 Role-Based Access Control (RBAC):**
    *   **Admin:** Full global visibility and system management across all projects.
    *   **Managers:** Isolated project management where managers can view, create, and oversee only their own managed projects.
    *   **Developers:** Focused, task-based access allowing developers to view assigned projects, mark tasks as complete, check off subtasks, and collaborate.
*   **📊 GitHub-Style Contribution Heatmap:**
    *   Tracks daily user productivity (tasks completed, subtasks finished, projects created, and comments posted) visualized with green activity level squares directly on the dashboard.
*   **👥 Profile & Security Management:**
    *   Custom profile image avatar uploads.
    *   Full name personalization.
    *   Secure password updating.
*   **📋 Advanced Task & Subtask Workflows:**
    *   Dynamic status badges (*In Progress* vs. *Completed*).
    *   Task reassigning capabilities for managers/admins.
    *   Interactive subtasks with completion strikethroughs and individual delete/done controls.
*   **💬 Real-Time Collaboration:**
    *   Activity comment streams with author tagging and timestamps for every task.
*   **📱 Modern UI/UX:**
    *   Sleek sliding navigation hamburger menu, responsive dashboard layout, and FontAwesome icons.

---

## 🛠️ Tech Stack

*   **Backend:** Python, Flask, Werkzeug (Secure Filename / Utilities)
*   **Database:** SQLite3 with parameterized queries and connection timeout safeguards
*   **Frontend:** HTML5, Jinja2 Templating, CSS3 (Grid & Flexbox)
*   **Icons & Fonts:** FontAwesome 6.4.0

---

## 📁 Project Structure

```text
Project management/
│
├── static/
│   ├── uploads/           # User-uploaded profile avatars
│   └── style.css          # Custom application styles and heatmap grid
│
├── templates/             # HTML Jinja2 templates
│   ├── add_project.html
│   ├── dashboard.html
│   ├── login.html
│   ├── profile.html
│   ├── project_detail.html
│   └── task_detail.html
│
├── app.py                 # Main Flask application routes and logic
├── database.py            # Database initialization script
├── project_manager.db     # SQLite database
└── README.md


---

## 👨‍💻 Author

**Omar Faruk Shaon**
* GitHub: [@Omarfarukshaon](https://github.com/Omarfarukshaon)

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).