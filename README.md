#  Cleanroom Communication & Management System

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

##📘 How to Use

🔐 Login
Select your role: Lead or Technician
or Create profile if you are a Technician

Use your credentials to log in and access your dashboard

🧑‍🔧 Technician Dashboard
View and complete assigned tasks

Submit task results with notes and file uploads

View task/component progress and team messages

🧑‍💼 Lead Dashboard
Create projects and tasks

Assign tasks to team members and link to components

Upload traveler documents and extract tasks

Approve or reject submissions

📁 Document Tools
Upload PDF/DOCX traveler files

Extract task lists starting from specific sections/pages

Assign previewed tasks to technicians

🔍 Excel Tools
Upload a spreadsheet with asset location data

Use the lookup tool to search by name, type, or ID



