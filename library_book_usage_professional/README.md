# LibraryOS — Library Book Usage Analysis System

A polished, responsive library circulation and analytics website for a beginner/intermediate Python project.

## Stack
- Python 3.10+
- Flask (web application)
- SQLite (database)
- Pandas + NumPy (data analysis)
- Chart.js (interactive browser charts)
- Bootstrap 5 + custom CSS (responsive UI)

## Quick start — Windows
1. Extract this ZIP archive.
2. Open the extracted `library_book_usage_professional` folder.
3. Click the File Explorer address bar, type `cmd`, and press Enter.
4. Run these commands one by one:

```bash
py -m venv venv
venv\Scripts\activate
py -m pip install -r requirements.txt
py app.py
```

If the `py` command is unavailable, use `python` instead.

5. Open http://127.0.0.1:5000 in Chrome or Edge.

## First login
- Username: `admin`
- Password: `admin123`

Change the default password from Settings immediately after your first login.

## Included modules
- Dashboard: total book copies, unique titles, borrowers, active loans, overdue loans, recent circulation and popular titles.
- Book catalogue: add, search and delete book records.
- Borrowers: register students with unique roll numbers and review transaction counts.
- Circulation: issue and return books, validate dates, reject unavailable copies and prevent duplicate returns.
- Analytics: monthly borrowing trend, category usage, most-borrowed books, overdue list and average borrowing duration.
- Reports: export all-loan, overdue and popular-book CSV files.
- Settings: update administrator password.

## Database rules
- SQLite database is created automatically as `library.db`.
- Foreign keys are enabled.
- Issuing and returning use SQLite write transactions to keep copy counts consistent.
- A due date cannot be earlier than an issue date.
- A return date cannot be earlier than its issue date.
- A book with an active loan cannot be deleted.
- Sample books and borrowers are inserted on first run.

## Project structure
```text
library_book_usage_professional/
├── app.py
├── requirements.txt
├── README.md
├── library.db              # created automatically on first run
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── books.html
│   ├── borrowers.html
│   ├── loans.html
│   ├── analytics.html
│   └── settings.html
└── static/
    └── style.css
```

## Troubleshooting
- `No module named flask`: activate the virtual environment and run `py -m pip install -r requirements.txt`.
- `Address already in use`: close the other Flask terminal or change the port in `app.run`.
- `py is not recognized`: install Python from python.org and enable “Add Python to PATH”, then use `python`.
- If the browser cannot connect, confirm that `py app.py` is still running in the terminal.

## Academic / deployment note
This is a local educational project. It uses a simple administrator login and is not hardened for public production deployment. Before exposing it to the internet, add CSRF protection, secure cookie settings, environment-managed secrets, rate limiting, role-based access, backups, audit logging, input validation, and a production WSGI server. Do not expose Flask debug mode publicly.
