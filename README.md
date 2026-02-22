# 🔥 Task To Reward App

A scalable, secure, fully admin-controlled web app where users earn money by completing tasks and uploading screenshots.

## 🧠 Core Logic
Users complete tasks → Upload screenshot → Admin verifies → Approved → Wallet credited → Withdrawal request → Admin manually pays → Upload proof → Mark as Paid.

## 🛠 Tech Stack
- **Backend:** Python (Flask)
- **Database:** SQLite (SQLAlchemy)
- **Frontend:** HTML, CSS (Bootstrap 5), JavaScript

## 🚀 Quick Start

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the App:**
   ```bash
   python app.py
   ```
   The app will automatically create the database and an admin user on the first run.

## 🔐 Credentials

### Admin Panel
- **URL:** `/login` (then redirected to `/admin/dashboard`)
- **Email:** `admin@tasktoreward.com`
- **Password:** `admin123`

### User Panel
- **URL:** `/register` or `/login`
- Users can create their own accounts.

## 📂 Project Structure
- `app.py`: Main application logic and routes.
- `models.py`: Database models for Users, Tasks, Submissions, etc.
- `templates/`: HTML templates for User and Admin panels.
- `static/uploads/`: Directory for uploaded screenshots and payment proofs.

## 📄 Terms & Policies
- Manual verification: 24-72 hours.
- One account per user rule.
- Fake screenshots result in account blocking.
- Admin decision is final.
