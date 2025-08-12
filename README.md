## Cleanroom Communication & Management System

A full-stack Django web application that simplifies communication, project tracking, and task assignment in cleanroom research environments.

> Built during my Summer 2025 LCLS Internship at SLAC National Accelerator Lab.

---

## 🚀 Features

- ✅ Role-based Login (Lead, Technician, Others)
- 🧠 Task creation, assignment, submission, and approval
- 📈 Dynamic project & component progress bars
- 💬 In-app project-based messaging
- 📁 Upload and extract tasks from PDF/DOCX traveler documents
- 🔍 Asset location lookup from Excel files
- 🧪 Future support for document-aware AI assistant (WIP)

---

## 🛠 Tech Stack

- **Backend**: Django, SQLite
- **Frontend**: HTML/JS, Tailwind CSS
- **Extras**: PyMuPDF, python-docx, openpyxl, pandas, channels, Redis

---
📂 Project Folder Structure

cleanroom-tracker/
│
├── backend/            #Django project files
│   ├── tracker/         # App containing most features
│   ├── templates/       # HTML templates for pages
│   ├── static/          # CSS, JavaScript, images
│   └── manage.py        # Main command file
│
├── requirements.txt     # List of required Python packages
└── README.md            # This file
---


## 📦 Installation

### 1. Clone the repo
```bash
git clone https://github.com/your-username/cleanroom-tracker.git
cd cleanroom-tracker

##2. Setup virtual environment
```bash
python -m venv venv
source venv/bin/activate   # or .\venv\Scripts\activate on Windows

##3. Install dependencies
```bash
pip install -r requirements.txt

##4. Run migrations
```bash
python manage.py migrate

##5. Start the development server
```bash
python manage.py runserver

Open your browser and go to: http://127.0.0.1:8000


##📘 How to Use

#Login
Go to the login page in your browser.

#Choose your role:

Lead – manage projects and assign tasks.

Technician – complete assigned tasks.

#Enter your username & password.

#Lead Dashboard
Create a Project – Name it, describe it, and add contributors.

Assign Tasks – Either create them manually or upload a traveler document to auto-extract.

Approve Submissions – Review technicians’ work and mark as approved/rejected.

Send Messages – Use in-app chat to communicate within each project.

#Technician Dashboard
View Assigned Tasks – See what you need to do and deadlines.

Submit Work – Upload files, photos, or notes directly to the task page.

Track Progress – Watch the task and project progress bars update.

Chat with Leads – Send/receive project messages without email.

#Document Tools
Upload PDF/DOCX traveler files.

Choose starting section/page for task extraction.

Review extracted tasks in the preview screen before assigning.

#Excel Asset Lookup
Upload an Excel file with asset locations.

Search by Asset Name, Type, or ID to find where it is stored.

#Maintenance & Troubleshooting
Restarting the Server:

```bash
python manage.py runserver
Creating a New Admin Account:

python manage.py createsuperuser

#If Something Breaks:

#Make sure the virtual environment is active.

#Run:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver


#Database Backups:

The main database is db.sqlite3 in the project folder.

Copy this file regularly to back up your data 