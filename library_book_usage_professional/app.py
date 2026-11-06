from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import date, datetime
import sqlite3, csv, io, os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
DB_PATH = os.path.join(os.path.dirname(__file__), "library.db")
FINE_DAYS_DEFAULT = 14

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS admins (
            admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS books (
            book_id INTEGER PRIMARY KEY AUTOINCREMENT,
            isbn TEXT UNIQUE,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            category TEXT NOT NULL,
            total_copies INTEGER NOT NULL CHECK(total_copies >= 0),
            copies_available INTEGER NOT NULL CHECK(copies_available >= 0)
        );
        CREATE TABLE IF NOT EXISTS borrowers (
            borrower_id INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_name TEXT NOT NULL,
            roll_no TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS loans (
            loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            borrower_id INTEGER NOT NULL,
            issue_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            return_date TEXT,
            FOREIGN KEY(book_id) REFERENCES books(book_id),
            FOREIGN KEY(borrower_id) REFERENCES borrowers(borrower_id),
            CHECK(due_date >= issue_date),
            CHECK(return_date IS NULL OR return_date >= issue_date)
        );
        CREATE INDEX IF NOT EXISTS idx_loans_dates ON loans(issue_date, due_date, return_date);
        """)
        admin = con.execute("SELECT admin_id FROM admins WHERE username='admin'").fetchone()
        if not admin:
            con.execute("INSERT INTO admins(username,password_hash) VALUES(?,?)",
                        ("admin", generate_password_hash("admin123")))
        count = con.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        if count == 0:
            sample_books = [
                ("9780131103627","The C Programming Language","Brian Kernighan","Programming",5,5),
                ("9780132350884","Clean Code","Robert C. Martin","Programming",4,4),
                ("9780262033848","Introduction to Algorithms","Thomas H. Cormen","Computer Science",3,3),
                ("978013.0001","Computer Networks","Andrew S. Tanenbaum","Networking",4,4),
                ("9780140449136","The Odyssey","Homer","Literature",2,2),
            ]
            con.executemany("""INSERT INTO books(isbn,title,author,category,total_copies,copies_available)
                               VALUES(?,?,?,?,?,?)""", sample_books)
            sample_borrowers = [("Aarav Kumar","BTECH001"),("Priya Sharma","BTECH002"),("Rahul Reddy","BTECH003")]
            con.executemany("INSERT INTO borrowers(borrower_name,roll_no) VALUES(?,?)", sample_borrowers)

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def overdue_condition(today=None):
    today = today or date.today().isoformat()
    return "return_date IS NULL AND due_date < ?", (today,)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        with db() as con:
            admin = con.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
        if admin and check_password_hash(admin["password_hash"], password):
            session["admin_id"] = admin["admin_id"]
            session["username"] = admin["username"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def dashboard():
    today = date.today().isoformat()
    with db() as con:
        stats = {
            "books": con.execute("SELECT COALESCE(SUM(total_copies),0) FROM books").fetchone()[0],
            "titles": con.execute("SELECT COUNT(*) FROM books").fetchone()[0],
            "borrowers": con.execute("SELECT COUNT(*) FROM borrowers").fetchone()[0],
            "active": con.execute("SELECT COUNT(*) FROM loans WHERE return_date IS NULL").fetchone()[0],
            "overdue": con.execute("SELECT COUNT(*) FROM loans WHERE return_date IS NULL AND due_date < ?",(today,)).fetchone()[0],
        }
        recent = con.execute("""SELECT l.*, b.title, br.borrower_name, br.roll_no
          FROM loans l JOIN books b USING(book_id) JOIN borrowers br USING(borrower_id)
          ORDER BY loan_id DESC LIMIT 7""").fetchall()
        popular = con.execute("""SELECT b.title, COUNT(l.loan_id) AS borrow_count
          FROM books b LEFT JOIN loans l USING(book_id)
          GROUP BY b.book_id ORDER BY borrow_count DESC, b.title LIMIT 5""").fetchall()
    return render_template("dashboard.html", stats=stats, recent=recent, popular=popular, today=today)

@app.route("/books", methods=["GET","POST"])
@login_required
def books():
    if request.method == "POST":
        action = request.form.get("action")
        try:
            with db() as con:
                if action == "add":
                    title=request.form["title"].strip(); author=request.form["author"].strip()
                    category=request.form["category"].strip(); isbn=request.form.get("isbn","").strip() or None
                    copies=int(request.form["total_copies"])
                    if not title or not author or not category or copies < 0: raise ValueError("Enter valid book details.")
                    con.execute("""INSERT INTO books(isbn,title,author,category,total_copies,copies_available)
                                   VALUES(?,?,?,?,?,?)""",(isbn,title,author,category,copies,copies))
                    flash("Book added successfully.","success")
                elif action == "delete":
                    bid=int(request.form["book_id"])
                    active=con.execute("SELECT COUNT(*) FROM loans WHERE book_id=? AND return_date IS NULL",(bid,)).fetchone()[0]
                    if active: raise ValueError("Cannot delete a book with active loans.")
                    con.execute("DELETE FROM books WHERE book_id=?",(bid,))
                    flash("Book deleted.","success")
        except sqlite3.IntegrityError:
            flash("ISBN already exists. Use a unique ISBN.","danger")
        except (ValueError, KeyError) as e:
            flash(str(e) or "Invalid input.","danger")
        return redirect(url_for("books"))
    q=request.args.get("q","").strip()
    with db() as con:
        if q:
            rows=con.execute("""SELECT * FROM books WHERE title LIKE ? OR author LIKE ? OR category LIKE ? OR isbn LIKE ? ORDER BY title""",
                             tuple([f"%{q}%"]*4)).fetchall()
        else: rows=con.execute("SELECT * FROM books ORDER BY title").fetchall()
    return render_template("books.html", books=rows, q=q)

@app.route("/borrowers", methods=["GET","POST"])
@login_required
def borrowers():
    if request.method=="POST":
        name=request.form.get("borrower_name","").strip(); roll=request.form.get("roll_no","").strip()
        try:
            if not name or not roll: raise ValueError("Name and roll number are required.")
            with db() as con:
                con.execute("INSERT INTO borrowers(borrower_name,roll_no) VALUES(?,?)",(name,roll))
            flash("Borrower registered.","success")
        except sqlite3.IntegrityError: flash("That roll number is already registered.","danger")
        except ValueError as e: flash(str(e),"danger")
        return redirect(url_for("borrowers"))
    with db() as con:
        rows=con.execute("""SELECT br.*, COUNT(l.loan_id) AS loan_count
          FROM borrowers br LEFT JOIN loans l USING(borrower_id)
          GROUP BY br.borrower_id ORDER BY br.borrower_name""").fetchall()
    return render_template("borrowers.html", borrowers=rows)

@app.route("/loans")
@login_required
def loans():
    status=request.args.get("status","all")
    sql="""SELECT l.*, b.title, br.borrower_name, br.roll_no,
      CASE WHEN l.return_date IS NOT NULL THEN 'Returned'
           WHEN l.due_date < date('now','localtime') THEN 'Overdue' ELSE 'Active' END AS status
      FROM loans l JOIN books b USING(book_id) JOIN borrowers br USING(borrower_id)"""
    if status=="active": sql += " WHERE l.return_date IS NULL AND l.due_date >= date('now','localtime')"
    elif status=="overdue": sql += " WHERE l.return_date IS NULL AND l.due_date < date('now','localtime')"
    elif status=="returned": sql += " WHERE l.return_date IS NOT NULL"
    sql += " ORDER BY l.loan_id DESC"
    with db() as con:
        rows=con.execute(sql).fetchall()
        books_list=con.execute("SELECT book_id,title,copies_available FROM books WHERE copies_available>0 ORDER BY title").fetchall()
        borrowers_list=con.execute("SELECT * FROM borrowers ORDER BY borrower_name").fetchall()
    return render_template("loans.html", loans=rows, books=books_list, borrowers=borrowers_list, status=status, today=date.today().isoformat())

@app.route("/issue", methods=["POST"])
@login_required
def issue():
    try:
        book_id=int(request.form["book_id"]); borrower_id=int(request.form["borrower_id"])
        issue_date=request.form["issue_date"]; due_date=request.form["due_date"]
        datetime.strptime(issue_date,"%Y-%m-%d"); datetime.strptime(due_date,"%Y-%m-%d")
        if due_date < issue_date: raise ValueError("Due date cannot be before issue date.")
        with db() as con:
            con.execute("BEGIN IMMEDIATE")
            book=con.execute("SELECT copies_available FROM books WHERE book_id=?",(book_id,)).fetchone()
            borrower=con.execute("SELECT borrower_id FROM borrowers WHERE borrower_id=?",(borrower_id,)).fetchone()
            if not book or not borrower: raise ValueError("Select a valid book and borrower.")
            if book["copies_available"] <= 0: raise ValueError("No copies are currently available.")
            con.execute("INSERT INTO loans(book_id,borrower_id,issue_date,due_date) VALUES(?,?,?,?)",
                        (book_id,borrower_id,issue_date,due_date))
            con.execute("UPDATE books SET copies_available=copies_available-1 WHERE book_id=?",(book_id,))
        flash("Book issued successfully.","success")
    except (ValueError, KeyError) as e: flash(str(e) or "Invalid issue details.","danger")
    except sqlite3.Error: flash("Could not issue book. Please check the selected records.","danger")
    return redirect(url_for("loans"))

@app.route("/return/<int:loan_id>", methods=["POST"])
@login_required
def return_book(loan_id):
    try:
        return_date=request.form.get("return_date") or date.today().isoformat()
        datetime.strptime(return_date,"%Y-%m-%d")
        with db() as con:
            con.execute("BEGIN IMMEDIATE")
            loan=con.execute("SELECT * FROM loans WHERE loan_id=?",(loan_id,)).fetchone()
            if not loan: raise ValueError("Loan record not found.")
            if loan["return_date"] is not None: raise ValueError("This book has already been returned.")
            if return_date < loan["issue_date"]: raise ValueError("Return date cannot be before issue date.")
            con.execute("UPDATE loans SET return_date=? WHERE loan_id=?",(return_date,loan_id))
            con.execute("UPDATE books SET copies_available=copies_available+1 WHERE book_id=?",(loan["book_id"],))
        flash("Book returned and available copies updated.","success")
    except ValueError as e: flash(str(e),"danger")
    except sqlite3.Error: flash("Could not process return.","danger")
    return redirect(url_for("loans"))

@app.route("/charts/<kind>.png")
@login_required
def chart_image(kind):
    with db() as con:
        if kind == "monthly":
            frame = pd.read_sql_query("SELECT issue_date FROM loans", con)
            fig, ax = plt.subplots(figsize=(8, 3.2))
            if not frame.empty:
                frame["month"] = pd.to_datetime(frame["issue_date"]).dt.to_period("M").astype(str)
                counts = frame.groupby("month").size()
                ax.plot(counts.index, counts.values, marker="o", linewidth=2)
                ax.set_ylabel("Borrowings")
                ax.tick_params(axis="x", rotation=35)
                ax.grid(axis="y", alpha=.2)
            else:
                ax.text(.5, .5, "No borrowing data yet", ha="center", va="center", transform=ax.transAxes)
                ax.set_xticks([]); ax.set_yticks([])
            ax.set_title("Monthly borrowing trend")
        elif kind == "category":
            frame = pd.read_sql_query("SELECT b.category, COUNT(l.loan_id) AS borrows FROM books b LEFT JOIN loans l USING(book_id) GROUP BY b.category ORDER BY borrows DESC", con)
            fig, ax = plt.subplots(figsize=(6, 3.2))
            if not frame.empty and frame["borrows"].sum() > 0:
                ax.bar(frame["category"], frame["borrows"])
                ax.set_ylabel("Borrow transactions")
                ax.tick_params(axis="x", rotation=25)
            else:
                ax.text(.5, .5, "No borrowing data yet", ha="center", va="center", transform=ax.transAxes)
                ax.set_xticks([]); ax.set_yticks([])
            ax.set_title("Borrowing by category")
        else:
            return "Unknown chart", 404
        fig.tight_layout()
        image = io.BytesIO()
        fig.savefig(image, format="png", dpi=140, bbox_inches="tight")
        plt.close(fig)
        image.seek(0)
        return send_file(image, mimetype="image/png")

@app.route("/analytics")
@login_required
def analytics():
    with db() as con:
        loan_df=pd.read_sql_query("""SELECT l.issue_date,l.due_date,l.return_date,b.title,b.category
          FROM loans l JOIN books b USING(book_id)""",con)
        category=con.execute("""SELECT b.category, COUNT(l.loan_id) AS borrows
          FROM books b LEFT JOIN loans l USING(book_id)
          GROUP BY b.category ORDER BY borrows DESC""").fetchall()
        popular=con.execute("""SELECT b.title, COUNT(l.loan_id) AS borrows
          FROM books b LEFT JOIN loans l USING(book_id)
          GROUP BY b.book_id ORDER BY borrows DESC,b.title LIMIT 10""").fetchall()
        overdue=con.execute("""SELECT l.loan_id,b.title,br.borrower_name,br.roll_no,l.due_date,
          CAST(julianday('now','localtime')-julianday(l.due_date) AS INTEGER) AS days_late
          FROM loans l JOIN books b USING(book_id) JOIN borrowers br USING(borrower_id)
          WHERE l.return_date IS NULL AND l.due_date < date('now','localtime')
          ORDER BY l.due_date""").fetchall()
    monthly={}
    if not loan_df.empty:
        loan_df["month"]=pd.to_datetime(loan_df["issue_date"]).dt.to_period("M").astype(str)
        monthly=loan_df.groupby("month").size().to_dict()
    avg_days=0
    if not loan_df.empty:
        returned=loan_df[loan_df["return_date"].notna()].copy()
        if not returned.empty:
            durations=(pd.to_datetime(returned["return_date"])-pd.to_datetime(returned["issue_date"])).dt.days
            avg_days=round(float(np.mean(durations)),1)
    return render_template("analytics.html", category=category, popular=popular, overdue=overdue,
                           monthly=monthly, avg_days=avg_days, total_transactions=len(loan_df))

@app.route("/report/<kind>")
@login_required
def report(kind):
    output=io.StringIO(); writer=csv.writer(output)
    with db() as con:
        if kind=="overdue":
            rows=con.execute("""SELECT l.loan_id,b.title,br.borrower_name,br.roll_no,l.issue_date,l.due_date
              FROM loans l JOIN books b USING(book_id) JOIN borrowers br USING(borrower_id)
              WHERE l.return_date IS NULL AND l.due_date < date('now','localtime') ORDER BY l.due_date""").fetchall()
            writer.writerow(["Loan ID","Book","Borrower","Roll No","Issue Date","Due Date"])
        elif kind=="popular":
            rows=con.execute("""SELECT b.title,b.author,b.category,COUNT(l.loan_id) AS borrows
              FROM books b LEFT JOIN loans l USING(book_id) GROUP BY b.book_id ORDER BY borrows DESC""").fetchall()
            writer.writerow(["Book","Author","Category","Borrow Count"])
        elif kind=="loans":
            rows=con.execute("""SELECT l.loan_id,b.title,br.borrower_name,br.roll_no,l.issue_date,l.due_date,l.return_date
              FROM loans l JOIN books b USING(book_id) JOIN borrowers br USING(borrower_id) ORDER BY l.loan_id DESC""").fetchall()
            writer.writerow(["Loan ID","Book","Borrower","Roll No","Issue Date","Due Date","Return Date"])
        else: return "Unknown report",404
        for row in rows: writer.writerow(list(row))
    mem=io.BytesIO(output.getvalue().encode("utf-8-sig")); mem.seek(0)
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name=f"{kind}_report.csv")

@app.route("/settings", methods=["GET","POST"])
@login_required
def settings():
    if request.method=="POST":
        old=request.form.get("old_password",""); new=request.form.get("new_password","")
        with db() as con:
            admin=con.execute("SELECT * FROM admins WHERE admin_id=?",(session["admin_id"],)).fetchone()
            if not check_password_hash(admin["password_hash"],old): flash("Current password is incorrect.","danger")
            elif len(new)<8: flash("New password must contain at least 8 characters.","danger")
            else:
                con.execute("UPDATE admins SET password_hash=? WHERE admin_id=?",(generate_password_hash(new),session["admin_id"]))
                flash("Password updated. Please remember your new password.","success")
        return redirect(url_for("settings"))
    return render_template("settings.html")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
