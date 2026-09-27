"""
Library Management System (LMS Pro)
A modern, attractive desktop application built with CustomTkinter and SQLite3.

Features:
- Complete database layer with automated migrations and seed data
- Modern flat UI with Dark/Light theme switching
- Dashboard with live KPI counters and recent transactions
- Book management (Add, Edit, Delete with active loan protection, Search, Sortable Table)
- Member management (Register, Edit, Delete with loan protection, Loan count tracking)
- Issue Book workflow (Max 3 books limit, zero-copy protection, 14-day loan)
- Return Book workflow (Live active loan selector, ₹5/day overdue fine calculation)
- Fast multi-criteria book search
"""

import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, date, timedelta
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

# ---------------------------------------------------------------------------
# Configuration & Constants
# ---------------------------------------------------------------------------
APP_TITLE = "Library Management System"
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library.db")
FINE_PER_DAY = 5.0  # ₹5 per day overdue
LOAN_PERIOD_DAYS = 14
MAX_ACTIVE_LOANS = 3

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# CustomTkinter Global Setup
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


# ---------------------------------------------------------------------------
# Database Management Layer
# ---------------------------------------------------------------------------
class DatabaseManager:
    """Handles all SQLite3 database operations and schema lifecycle."""

    def __init__(self, db_path=DB_FILE):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Creates tables if they don't exist and seeds initial data if database is new."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS books (
                    book_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    category TEXT,
                    isbn TEXT UNIQUE NOT NULL,
                    total_copies INTEGER NOT NULL,
                    available_copies INTEGER NOT NULL
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS members (
                    member_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    contact TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    address TEXT,
                    membership_date TEXT NOT NULL
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    member_id INTEGER NOT NULL,
                    book_id INTEGER NOT NULL,
                    issue_date TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    return_date TEXT,
                    fine REAL DEFAULT 0,
                    status TEXT NOT NULL CHECK(status IN ('Issued', 'Returned')),
                    FOREIGN KEY (member_id) REFERENCES members (member_id),
                    FOREIGN KEY (book_id) REFERENCES books (book_id)
                );
            """)

            # Seed demo data if database is newly initialized
            cursor.execute("SELECT COUNT(*) FROM books;")
            if cursor.fetchone()[0] == 0:
                self._seed_sample_data(cursor)
            conn.commit()

    def _seed_sample_data(self, cursor):
        """Populates realistic demo data for first run."""
        sample_books = [
            ("To Kill a Mockingbird", "Harper Lee", "Fiction", "9780061120084", 5, 4),
            ("1984", "George Orwell", "Dystopian", "9780451524935", 4, 3),
            ("Clean Code", "Robert C. Martin", "Computer Science", "9780132350884", 3, 2),
            ("A Brief History of Time", "Stephen Hawking", "Science", "9780553380163", 4, 4),
            ("The Great Gatsby", "F. Scott Fitzgerald", "Classic", "9780743273565", 3, 3),
            ("Python Crash Course", "Eric Matthes", "Computer Science", "9781593279288", 5, 5),
            ("Sapiens: A Brief History", "Yuval Noah Harari", "History", "9780062316097", 4, 4),
        ]
        cursor.executemany("""
            INSERT INTO books (title, author, category, isbn, total_copies, available_copies)
            VALUES (?, ?, ?, ?, ?, ?);
        """, sample_books)

        today_str = date.today().isoformat()
        sample_members = [
            ("Alice Johnson", "+91 9876543210", "alice.johnson@example.com", "12 Maple Street, Mumbai", today_str),
            ("Bob Smith", "+91 9811223344", "bob.smith@example.com", "45 Park Avenue, Bangalore", today_str),
            ("Charlie Davis", "+91 9922334455", "charlie.d@example.com", "88 Residency Road, Delhi", today_str),
            ("David Miller", "+91 9733445566", "david.m@example.com", "102 Lake View, Pune", today_str),
        ]
        cursor.executemany("""
            INSERT INTO members (name, contact, email, address, membership_date)
            VALUES (?, ?, ?, ?, ?);
        """, sample_members)

        # Seed sample active & returned transactions
        # 1. On-time active loan for Alice (Book 1)
        issue_1 = (date.today() - timedelta(days=4)).isoformat()
        due_1 = (date.today() + timedelta(days=10)).isoformat()
        # 2. Overdue active loan for Bob (Book 2) - overdue by 3 days
        issue_2 = (date.today() - timedelta(days=17)).isoformat()
        due_2 = (date.today() - timedelta(days=3)).isoformat()
        # 3. Active loan for Charlie (Book 3)
        issue_3 = (date.today() - timedelta(days=2)).isoformat()
        due_3 = (date.today() + timedelta(days=12)).isoformat()
        # 4. Returned loan
        issue_4 = (date.today() - timedelta(days=25)).isoformat()
        due_4 = (date.today() - timedelta(days=11)).isoformat()
        return_4 = (date.today() - timedelta(days=11)).isoformat()

        sample_txs = [
            (1, 1, issue_1, due_1, None, 0.0, "Issued"),
            (2, 2, issue_2, due_2, None, 0.0, "Issued"),
            (3, 3, issue_3, due_3, None, 0.0, "Issued"),
            (1, 4, issue_4, due_4, return_4, 0.0, "Returned"),
        ]
        cursor.executemany("""
            INSERT INTO transactions (member_id, book_id, issue_date, due_date, return_date, fine, status)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, sample_txs)

    # ------------------ Books CRUD ------------------
    def add_book(self, title, author, category, isbn, total_copies):
        title = title.strip()
        author = author.strip()
        category = category.strip()
        isbn = isbn.strip()

        if not title or not author or not isbn:
            raise ValueError("Title, Author, and ISBN are required fields.")
        if total_copies <= 0:
            raise ValueError("Total copies must be a positive integer.")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT book_id FROM books WHERE isbn = ?;", (isbn,))
            if cursor.fetchone():
                raise ValueError(f"A book with ISBN '{isbn}' already exists.")

            cursor.execute("""
                INSERT INTO books (title, author, category, isbn, total_copies, available_copies)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (title, author, category, isbn, total_copies, total_copies))
            conn.commit()
            return cursor.lastrowid

    def update_book(self, book_id, title, author, category, isbn, total_copies):
        title = title.strip()
        author = author.strip()
        category = category.strip()
        isbn = isbn.strip()

        if not title or not author or not isbn:
            raise ValueError("Title, Author, and ISBN are required fields.")
        if total_copies <= 0:
            raise ValueError("Total copies must be a positive integer.")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT book_id FROM books WHERE isbn = ? AND book_id != ?;", (isbn, book_id))
            if cursor.fetchone():
                raise ValueError(f"Another book with ISBN '{isbn}' already exists.")

            # Calculate active loans to preserve copy consistency
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE book_id = ? AND status = 'Issued';", (book_id,))
            active_loans = cursor.fetchone()[0]

            if total_copies < active_loans:
                raise ValueError(f"Total copies cannot be less than currently active loans ({active_loans}).")

            available_copies = total_copies - active_loans

            cursor.execute("""
                UPDATE books
                SET title = ?, author = ?, category = ?, isbn = ?, total_copies = ?, available_copies = ?
                WHERE book_id = ?;
            """, (title, author, category, isbn, total_copies, available_copies, book_id))
            conn.commit()

    def delete_book(self, book_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE book_id = ? AND status = 'Issued';", (book_id,))
            active_loans = cursor.fetchone()[0]
            if active_loans > 0:
                raise ValueError(f"Cannot delete book: There are {active_loans} active loan(s) for this book.")

            # Delete historical transactions and book
            cursor.execute("DELETE FROM transactions WHERE book_id = ?;", (book_id,))
            cursor.execute("DELETE FROM books WHERE book_id = ?;", (book_id,))
            conn.commit()

    def get_book(self, book_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM books WHERE book_id = ?;", (book_id,))
            return cursor.fetchone()

    def get_all_books(self, search_query="", search_field="All"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = search_query.strip()
            if not query:
                cursor.execute("SELECT * FROM books ORDER BY book_id DESC;")
                return cursor.fetchall()

            pattern = f"%{query}%"
            if search_field == "Title":
                cursor.execute("SELECT * FROM books WHERE title LIKE ? ORDER BY book_id DESC;", (pattern,))
            elif search_field == "Author":
                cursor.execute("SELECT * FROM books WHERE author LIKE ? ORDER BY book_id DESC;", (pattern,))
            elif search_field == "ISBN":
                cursor.execute("SELECT * FROM books WHERE isbn LIKE ? ORDER BY book_id DESC;", (pattern,))
            elif search_field == "Category":
                cursor.execute("SELECT * FROM books WHERE category LIKE ? ORDER BY book_id DESC;", (pattern,))
            else:  # All
                cursor.execute("""
                    SELECT * FROM books
                    WHERE title LIKE ? OR author LIKE ? OR isbn LIKE ? OR category LIKE ?
                    ORDER BY book_id DESC;
                """, (pattern, pattern, pattern, pattern))
            return cursor.fetchall()

    # ------------------ Members CRUD ------------------
    def add_member(self, name, contact, email, address):
        name = name.strip()
        contact = contact.strip()
        email = email.strip()
        address = address.strip()

        if not name or not contact or not email:
            raise ValueError("Name, Contact, and Email are required fields.")

        if not EMAIL_REGEX.match(email):
            raise ValueError("Invalid email format (e.g. user@example.com).")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT member_id FROM members WHERE LOWER(email) = LOWER(?);", (email,))
            if cursor.fetchone():
                raise ValueError("Duplicate email: A member with this email is already registered.")

            today_str = date.today().isoformat()
            cursor.execute("""
                INSERT INTO members (name, contact, email, address, membership_date)
                VALUES (?, ?, ?, ?, ?);
            """, (name, contact, email, address, today_str))
            conn.commit()
            return cursor.lastrowid

    def update_member(self, member_id, name, contact, email, address):
        name = name.strip()
        contact = contact.strip()
        email = email.strip()
        address = address.strip()

        if not name or not contact or not email:
            raise ValueError("Name, Contact, and Email are required fields.")

        if not EMAIL_REGEX.match(email):
            raise ValueError("Invalid email format (e.g. user@example.com).")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT member_id FROM members WHERE LOWER(email) = LOWER(?) AND member_id != ?;", (email, member_id))
            if cursor.fetchone():
                raise ValueError("Duplicate email: Another member with this email already exists.")

            cursor.execute("""
                UPDATE members
                SET name = ?, contact = ?, email = ?, address = ?
                WHERE member_id = ?;
            """, (name, contact, email, address, member_id))
            conn.commit()

    def delete_member(self, member_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE member_id = ? AND status = 'Issued';", (member_id,))
            active_loans = cursor.fetchone()[0]
            if active_loans > 0:
                raise ValueError(f"Cannot delete member: Member has {active_loans} active unreturned loan(s).")

            cursor.execute("DELETE FROM transactions WHERE member_id = ?;", (member_id,))
            cursor.execute("DELETE FROM members WHERE member_id = ?;", (member_id,))
            conn.commit()

    def get_member(self, member_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM members WHERE member_id = ?;", (member_id,))
            return cursor.fetchone()

    def get_all_members(self, search_query=""):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = search_query.strip()
            sql = """
                SELECT m.member_id, m.name, m.contact, m.email, m.address, m.membership_date,
                       (SELECT COUNT(*) FROM transactions t WHERE t.member_id = m.member_id AND t.status = 'Issued') as active_loans
                FROM members m
            """
            if query:
                sql += " WHERE m.name LIKE ? OR m.email LIKE ? OR m.contact LIKE ?"
                sql += " ORDER BY m.member_id DESC;"
                pattern = f"%{query}%"
                cursor.execute(sql, (pattern, pattern, pattern))
            else:
                sql += " ORDER BY m.member_id DESC;"
                cursor.execute(sql)
            return cursor.fetchall()

    def get_member_active_loans_count(self, member_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE member_id = ? AND status = 'Issued';", (member_id,))
            return cursor.fetchone()[0]

    # ------------------ Issue & Return ------------------
    def issue_book(self, member_id, book_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Check member
            cursor.execute("SELECT name FROM members WHERE member_id = ?;", (member_id,))
            member = cursor.fetchone()
            if not member:
                raise ValueError("Member not found: Invalid Member ID.")

            # 2. Check book
            cursor.execute("SELECT title, available_copies FROM books WHERE book_id = ?;", (book_id,))
            book = cursor.fetchone()
            if not book:
                raise ValueError("Book not found: Invalid Book ID.")

            # 3. Check copies
            if book["available_copies"] <= 0:
                raise ValueError("No copies available: All copies of this book are currently issued.")

            # 4. Check borrow limit
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE member_id = ? AND status = 'Issued';", (member_id,))
            active_loans = cursor.fetchone()[0]
            if active_loans >= MAX_ACTIVE_LOANS:
                raise ValueError(f"Borrow limit reached: Member already has {active_loans} active loans (max {MAX_ACTIVE_LOANS} books).")

            # 5. Insert transaction & decrement copies
            today = date.today()
            due = today + timedelta(days=LOAN_PERIOD_DAYS)

            cursor.execute("""
                INSERT INTO transactions (member_id, book_id, issue_date, due_date, status, fine)
                VALUES (?, ?, ?, ?, 'Issued', 0);
            """, (member_id, book_id, today.isoformat(), due.isoformat()))
            tx_id = cursor.lastrowid

            cursor.execute("""
                UPDATE books SET available_copies = available_copies - 1 WHERE book_id = ?;
            """, (book_id,))

            conn.commit()
            return {
                "transaction_id": tx_id,
                "member_name": member["name"],
                "book_title": book["title"],
                "issue_date": today.isoformat(),
                "due_date": due.isoformat()
            }

    def return_book(self, transaction_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Fetch transaction
            cursor.execute("""
                SELECT t.transaction_id, t.member_id, t.book_id, t.issue_date, t.due_date, t.status,
                       b.title as book_title, m.name as member_name
                FROM transactions t
                JOIN books b ON t.book_id = b.book_id
                JOIN members m ON t.member_id = m.member_id
                WHERE t.transaction_id = ?;
            """, (transaction_id,))
            tx = cursor.fetchone()

            if not tx:
                raise ValueError("Invalid transaction: Transaction ID not found.")
            if tx["status"] != "Issued":
                raise ValueError("Invalid transaction: This book has already been returned.")

            # 2. Calculate overdue fine
            today = date.today()
            due_date = date.fromisoformat(tx["due_date"])
            overdue_days = max(0, (today - due_date).days)
            fine = overdue_days * FINE_PER_DAY

            # 3. Update transaction & increment available copies
            cursor.execute("""
                UPDATE transactions
                SET return_date = ?, fine = ?, status = 'Returned'
                WHERE transaction_id = ?;
            """, (today.isoformat(), fine, transaction_id))

            cursor.execute("""
                UPDATE books SET available_copies = available_copies + 1 WHERE book_id = ?;
            """, (tx["book_id"],))

            conn.commit()
            return {
                "transaction_id": transaction_id,
                "member_name": tx["member_name"],
                "book_title": tx["book_title"],
                "due_date": tx["due_date"],
                "return_date": today.isoformat(),
                "overdue_days": overdue_days,
                "fine": fine
            }

    def get_active_transactions(self, search_query=""):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                SELECT t.transaction_id, t.member_id, m.name as member_name,
                       t.book_id, b.title as book_title, t.issue_date, t.due_date,
                       t.status
                FROM transactions t
                JOIN books b ON t.book_id = b.book_id
                JOIN members m ON t.member_id = m.member_id
                WHERE t.status = 'Issued'
            """
            query = search_query.strip()
            if query:
                sql += " AND (m.name LIKE ? OR b.title LIKE ? OR t.transaction_id = ?)"
                sql += " ORDER BY t.due_date ASC;"
                pattern = f"%{query}%"
                cursor.execute(sql, (pattern, pattern, query if query.isdigit() else -1))
            else:
                sql += " ORDER BY t.due_date ASC;"
                cursor.execute(sql)
            return cursor.fetchall()

    def get_recent_transactions(self, limit=10):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.transaction_id, m.name as member_name, b.title as book_title,
                       t.issue_date, t.due_date, t.return_date, t.fine, t.status
                FROM transactions t
                JOIN books b ON t.book_id = b.book_id
                JOIN members m ON t.member_id = m.member_id
                ORDER BY t.transaction_id DESC
                LIMIT ?;
            """, (limit,))
            return cursor.fetchall()

    def get_dashboard_stats(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_copies), 0), COALESCE(SUM(available_copies), 0) FROM books;")
            book_row = cursor.fetchone()
            total_titles = book_row[0]
            total_copies = book_row[1]
            avail_copies = book_row[2]

            cursor.execute("SELECT COUNT(*) FROM members;")
            total_members = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'Issued';")
            active_loans = cursor.fetchone()[0]

            today_str = date.today().isoformat()
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'Issued' AND due_date < ?;", (today_str,))
            overdue_count = cursor.fetchone()[0]

            cursor.execute("SELECT COALESCE(SUM(fine), 0) FROM transactions;")
            total_fines = cursor.fetchone()[0]

            return {
                "total_titles": total_titles,
                "total_copies": total_copies,
                "available_copies": avail_copies,
                "total_members": total_members,
                "active_loans": active_loans,
                "overdue_count": overdue_count,
                "total_fines": total_fines
            }


# ---------------------------------------------------------------------------
# Treeview Custom Styler Helper
# ---------------------------------------------------------------------------
def style_treeview(mode="Dark"):
    """Configures the ttk.Treeview widget colors to harmoniously match CustomTkinter."""
    style = ttk.Style()
    style.theme_use("clam")

    if mode == "Dark":
        bg_color = "#1e293b"       # slate-800
        fg_color = "#f8fafc"       # slate-50
        header_bg = "#0f172a"      # slate-900
        header_fg = "#94a3b8"      # slate-400
        selected_bg = "#2563eb"    # blue-600
        row_alt = "#172033"        # darker row
    else:
        bg_color = "#ffffff"
        fg_color = "#0f172a"
        header_bg = "#e2e8f0"
        header_fg = "#334155"
        selected_bg = "#3b82f6"
        row_alt = "#f8fafc"

    style.configure("Treeview",
                    background=bg_color,
                    foreground=fg_color,
                    fieldbackground=bg_color,
                    rowheight=32,
                    font=("Segoe UI", 11),
                    borderwidth=0)

    style.map("Treeview",
              background=[("selected", selected_bg)],
              foreground=[("selected", "#ffffff")])

    style.configure("Treeview.Heading",
                    background=header_bg,
                    foreground=header_fg,
                    font=("Segoe UI", 11, "bold"),
                    padding=(10, 8),
                    borderwidth=0)

    style.map("Treeview.Heading",
              background=[("active", "#334155" if mode == "Dark" else "#cbd5e1")],
              foreground=[("active", "#ffffff" if mode == "Dark" else "#0f172a")])


# ---------------------------------------------------------------------------
# UI Views & Components
# ---------------------------------------------------------------------------

class BaseView(ctk.CTkFrame):
    """Base class for all views providing common navigation and notifications."""

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.db = controller.db

    def refresh(self):
        """Hook called when view becomes visible."""
        pass


# ---------------------------------------------------------------------------
# 1. Dashboard View
# ---------------------------------------------------------------------------
class DashboardView(BaseView):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        # Main scrollable canvas/frame
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Header Title
        header_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 20))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="📊 Library Dashboard",
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold")
        )
        title_lbl.pack(side="left")

        today_lbl = ctk.CTkLabel(
            header_frame,
            text=f"Today: {date.today().strftime('%A, %d %B %Y')}",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=("gray40", "gray70")
        )
        today_lbl.pack(side="right")

        # KPI Metric Cards Container
        self.kpi_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.kpi_container.pack(fill="x", pady=(0, 20))
        self.kpi_container.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="kpi")

        self.card_books = self._create_kpi_card(
            self.kpi_container, 0, "Total Books", "0 Titles", "0 copies total", "📚", "#2563eb"
        )
        self.card_members = self._create_kpi_card(
            self.kpi_container, 1, "Registered Members", "0", "active readers", "👥", "#0d9488"
        )
        self.card_loans = self._create_kpi_card(
            self.kpi_container, 2, "Active Loans", "0", "currently issued", "🔄", "#d97706"
        )
        self.card_overdue = self._create_kpi_card(
            self.kpi_container, 3, "Overdue Books", "0", "fine applying", "⚠️", "#dc2626"
        )

        # Quick Actions Panel
        qa_frame = ctk.CTkFrame(self.scroll_frame, corner_radius=12)
        qa_frame.pack(fill="x", pady=(0, 20), ipady=10)

        qa_title = ctk.CTkLabel(
            qa_frame,
            text="⚡ Quick Actions",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")
        )
        qa_title.pack(anchor="w", padx=20, pady=(10, 10))

        btn_row = ctk.CTkFrame(qa_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=20)
        btn_row.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkButton(
            btn_row, text="🔄 Issue Book", font=ctk.CTkFont(size=14, weight="bold"),
            height=40, fg_color="#2563eb", hover_color="#1d4ed8",
            command=lambda: self.controller.show_view("IssueBookView")
        ).grid(row=0, column=0, padx=6, sticky="ew")

        ctk.CTkButton(
            btn_row, text="📥 Return Book", font=ctk.CTkFont(size=14, weight="bold"),
            height=40, fg_color="#059669", hover_color="#047857",
            command=lambda: self.controller.show_view("ReturnBookView")
        ).grid(row=0, column=1, padx=6, sticky="ew")

        ctk.CTkButton(
            btn_row, text="➕ Add Book", font=ctk.CTkFont(size=14, weight="bold"),
            height=40, fg_color="#4f46e5", hover_color="#4338ca",
            command=lambda: self.controller.show_view("AddBookView")
        ).grid(row=0, column=2, padx=6, sticky="ew")

        ctk.CTkButton(
            btn_row, text="👤 Register Member", font=ctk.CTkFont(size=14, weight="bold"),
            height=40, fg_color="#0891b2", hover_color="#0e7490",
            command=lambda: self.controller.show_view("RegisterMemberView")
        ).grid(row=0, column=3, padx=6, sticky="ew")

        # Recent Transactions Section
        recent_card = ctk.CTkFrame(self.scroll_frame, corner_radius=12)
        recent_card.pack(fill="both", expand=True)

        rec_header = ctk.CTkFrame(recent_card, fg_color="transparent")
        rec_header.pack(fill="x", padx=20, pady=(15, 10))

        ctk.CTkLabel(
            rec_header,
            text="🕒 Recent Activity / Transactions",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")
        ).pack(side="left")

        ctk.CTkButton(
            rec_header,
            text="🔄 Refresh",
            width=90,
            height=30,
            command=self.refresh
        ).pack(side="right")

        # Treeview for recent activity
        tree_container = ctk.CTkFrame(recent_card, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        columns = ("tx_id", "member", "book", "issue_date", "due_date", "status", "fine")
        self.tree = ttk.Treeview(tree_container, columns=columns, show="headings", height=8, selectmode="browse")

        self.tree.heading("tx_id", text="Tx ID")
        self.tree.heading("member", text="Member Name")
        self.tree.heading("book", text="Book Title")
        self.tree.heading("issue_date", text="Issued Date")
        self.tree.heading("due_date", text="Due Date")
        self.tree.heading("status", text="Status")
        self.tree.heading("fine", text="Fine (₹)")

        self.tree.column("tx_id", width=65, anchor="center")
        self.tree.column("member", width=180, anchor="w")
        self.tree.column("book", width=220, anchor="w")
        self.tree.column("issue_date", width=110, anchor="center")
        self.tree.column("due_date", width=110, anchor="center")
        self.tree.column("status", width=95, anchor="center")
        self.tree.column("fine", width=80, anchor="center")

        tree_scroll = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

    def _create_kpi_card(self, parent, col, title, value, subtitle, icon, accent_color):
        card = ctk.CTkFrame(parent, corner_radius=12)
        card.grid(row=0, column=col, padx=8, sticky="nsew")

        # Color indicator stripe
        stripe = ctk.CTkFrame(card, height=4, fg_color=accent_color, corner_radius=2)
        stripe.pack(fill="x", padx=10, pady=(6, 8))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        top_row = ctk.CTkFrame(inner, fg_color="transparent")
        top_row.pack(fill="x")

        title_lbl = ctk.CTkLabel(
            top_row, text=title, font=ctk.CTkFont(size=13, weight="normal"),
            text_color=("gray40", "gray70")
        )
        title_lbl.pack(side="left")

        icon_lbl = ctk.CTkLabel(top_row, text=icon, font=ctk.CTkFont(size=18))
        icon_lbl.pack(side="right")

        val_lbl = ctk.CTkLabel(
            inner, text=value, font=ctk.CTkFont(size=26, weight="bold"),
            text_color=accent_color
        )
        val_lbl.pack(anchor="w", pady=(6, 2))

        sub_lbl = ctk.CTkLabel(
            inner, text=subtitle, font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60")
        )
        sub_lbl.pack(anchor="w")

        return {"val_lbl": val_lbl, "sub_lbl": sub_lbl}

    def refresh(self):
        stats = self.db.get_dashboard_stats()
        self.card_books["val_lbl"].configure(text=f"{stats['total_titles']} Titles")
        self.card_books["sub_lbl"].configure(text=f"{stats['available_copies']} of {stats['total_copies']} copies available")

        self.card_members["val_lbl"].configure(text=str(stats["total_members"]))
        self.card_members["sub_lbl"].configure(text="registered readers")

        self.card_loans["val_lbl"].configure(text=str(stats["active_loans"]))
        self.card_loans["sub_lbl"].configure(text="books currently out")

        self.card_overdue["val_lbl"].configure(text=str(stats["overdue_count"]))
        self.card_overdue["sub_lbl"].configure(text=f"Total fines: ₹{stats['total_fines']:.1f}")

        # Refresh recent transactions
        for item in self.tree.get_children():
            self.tree.delete(item)

        rows = self.db.get_recent_transactions(12)
        today = date.today().isoformat()
        for r in rows:
            # Add warning tag if overdue & issued
            tag = "normal"
            if r["status"] == "Issued" and r["due_date"] < today:
                tag = "overdue"
            elif r["status"] == "Returned":
                tag = "returned"

            self.tree.insert(
                "", "end",
                values=(
                    f"#{r['transaction_id']}",
                    r["member_name"],
                    r["book_title"],
                    r["issue_date"],
                    r["due_date"],
                    r["status"],
                    f"₹{r['fine']:.2f}"
                ),
                tags=(tag,)
            )

        self.tree.tag_configure("overdue", foreground="#ef4444")
        self.tree.tag_configure("returned", foreground="#10b981")


# ---------------------------------------------------------------------------
# 2. Add Book View
# ---------------------------------------------------------------------------
class AddBookView(BaseView):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        # Center card container
        card = ctk.CTkFrame(self, corner_radius=14)
        card.pack(fill="both", expand=True, padx=40, pady=30)

        # Header
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=35, pady=(30, 20))

        ctk.CTkLabel(
            head, text="➕ Add New Book",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            head,
            text="Enter book details below. Available copies will automatically match total copies on registration.",
            font=ctk.CTkFont(size=13),
            text_color=("gray40", "gray70")
        ).pack(anchor="w", pady=(4, 0))

        # Form fields layout
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=35, pady=10)
        form.grid_columnconfigure((0, 1), weight=1)

        # Row 0: Title
        ctk.CTkLabel(form, text="Book Title *", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(5, 3))
        self.entry_title = ctk.CTkEntry(form, placeholder_text="e.g. Clean Code: A Handbook of Agile Software Craftsmanship", height=42, font=ctk.CTkFont(size=14))
        self.entry_title.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 16))

        # Row 1: Author & Category
        ctk.CTkLabel(form, text="Author *", font=ctk.CTkFont(size=14, weight="bold")).grid(row=2, column=0, sticky="w", pady=(5, 3), padx=(0, 10))
        self.entry_author = ctk.CTkEntry(form, placeholder_text="e.g. Robert C. Martin", height=42, font=ctk.CTkFont(size=14))
        self.entry_author.grid(row=3, column=0, sticky="ew", pady=(0, 16), padx=(0, 10))

        ctk.CTkLabel(form, text="Category / Genre", font=ctk.CTkFont(size=14, weight="bold")).grid(row=2, column=1, sticky="w", pady=(5, 3), padx=(10, 0))
        self.combo_category = ctk.CTkComboBox(
            form,
            values=["Computer Science", "Fiction", "Non-Fiction", "Science", "History", "Literature", "Philosophy", "Biography", "Business", "Mathematics", "Other"],
            height=42, font=ctk.CTkFont(size=14)
        )
        self.combo_category.set("Computer Science")
        self.combo_category.grid(row=3, column=1, sticky="ew", pady=(0, 16), padx=(10, 0))

        # Row 2: ISBN & Total Copies
        ctk.CTkLabel(form, text="ISBN (Unique Identifier) *", font=ctk.CTkFont(size=14, weight="bold")).grid(row=4, column=0, sticky="w", pady=(5, 3), padx=(0, 10))
        self.entry_isbn = ctk.CTkEntry(form, placeholder_text="e.g. 9780132350884", height=42, font=ctk.CTkFont(size=14))
        self.entry_isbn.grid(row=5, column=0, sticky="ew", pady=(0, 16), padx=(0, 10))

        ctk.CTkLabel(form, text="Total Copies *", font=ctk.CTkFont(size=14, weight="bold")).grid(row=4, column=1, sticky="w", pady=(5, 3), padx=(10, 0))
        self.entry_copies = ctk.CTkEntry(form, placeholder_text="e.g. 5", height=42, font=ctk.CTkFont(size=14))
        self.entry_copies.insert(0, "1")
        self.entry_copies.grid(row=5, column=1, sticky="ew", pady=(0, 16), padx=(10, 0))

        # Buttons
        btn_box = ctk.CTkFrame(card, fg_color="transparent")
        btn_box.pack(fill="x", padx=35, pady=(20, 35))

        self.btn_save = ctk.CTkButton(
            btn_box,
            text="💾 Save & Register Book",
            height=46,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=self._save_book
        )
        self.btn_save.pack(side="left", padx=(0, 15))

        self.btn_clear = ctk.CTkButton(
            btn_box,
            text="🧹 Clear Fields",
            height=46,
            width=120,
            font=ctk.CTkFont(size=14),
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            text_color=("black", "white"),
            command=self.clear_form
        )
        self.btn_clear.pack(side="left")

    def _save_book(self):
        title = self.entry_title.get()
        author = self.entry_author.get()
        category = self.combo_category.get()
        isbn = self.entry_isbn.get()
        copies_str = self.entry_copies.get().strip()

        if not copies_str.isdigit():
            messagebox.showerror("Validation Error", "Total copies must be a valid positive number.")
            return

        total_copies = int(copies_str)

        try:
            book_id = self.db.add_book(title, author, category, isbn, total_copies)
            messagebox.showinfo("Success", f"Book registered successfully!\n\nID: #{book_id}\nTitle: {title}\nCopies: {total_copies}")
            self.clear_form()
            self.controller.refresh_all_views()
        except ValueError as e:
            messagebox.showerror("Error Adding Book", str(e))
        except Exception as e:
            messagebox.showerror("System Error", f"An unexpected error occurred: {e}")

    def clear_form(self):
        self.entry_title.delete(0, "end")
        self.entry_author.delete(0, "end")
        self.entry_isbn.delete(0, "end")
        self.entry_copies.delete(0, "end")
        self.entry_copies.insert(0, "1")
        self.combo_category.set("Computer Science")


# ---------------------------------------------------------------------------
# 3. View / Manage Books View
# ---------------------------------------------------------------------------
class ViewBooksView(BaseView):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.sort_column = "book_id"
        self.sort_descending = False

        card = ctk.CTkFrame(self, corner_radius=14)
        card.pack(fill="both", expand=True, padx=25, pady=25)

        # Header with Search & Controls
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 15))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box, text="📚 Book Catalog & Inventory",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold")
        ).pack(anchor="w")

        self.count_lbl = ctk.CTkLabel(
            title_box, text="Showing 0 books", font=ctk.CTkFont(size=13),
            text_color=("gray40", "gray70")
        )
        self.count_lbl.pack(anchor="w")

        # Search Bar
        search_box = ctk.CTkFrame(header, fg_color="transparent")
        search_box.pack(side="right")

        self.search_entry = ctk.CTkEntry(
            search_box, placeholder_text="🔍 Filter by title, author, or ISBN...",
            width=260, height=36
        )
        self.search_entry.pack(side="left", padx=(0, 8))
        self.search_entry.bind("<KeyRelease>", lambda event: self.load_data())

        ctk.CTkButton(
            search_box, text="Refresh", width=80, height=36,
            command=self.load_data
        ).pack(side="left")

        # Treeview Data Table
        table_frame = ctk.CTkFrame(card, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        columns = ("book_id", "title", "author", "category", "isbn", "total_copies", "available_copies", "status")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("book_id", text="ID ↕", command=lambda: self._sort_by("book_id"))
        self.tree.heading("title", text="Title ↕", command=lambda: self._sort_by("title"))
        self.tree.heading("author", text="Author ↕", command=lambda: self._sort_by("author"))
        self.tree.heading("category", text="Category ↕", command=lambda: self._sort_by("category"))
        self.tree.heading("isbn", text="ISBN ↕", command=lambda: self._sort_by("isbn"))
        self.tree.heading("total_copies", text="Total ↕", command=lambda: self._sort_by("total_copies"))
        self.tree.heading("available_copies", text="Available ↕", command=lambda: self._sort_by("available_copies"))
        self.tree.heading("status", text="Stock Status")

        self.tree.column("book_id", width=50, anchor="center")
        self.tree.column("title", width=240, anchor="w")
        self.tree.column("author", width=160, anchor="w")
        self.tree.column("category", width=120, anchor="w")
        self.tree.column("isbn", width=120, anchor="center")
        self.tree.column("total_copies", width=70, anchor="center")
        self.tree.column("available_copies", width=80, anchor="center")
        self.tree.column("status", width=110, anchor="center")

        tree_scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        tree_scroll_x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll_y.pack(side="right", fill="y")

        # Bottom Actions Bar
        actions_bar = ctk.CTkFrame(card, fg_color="transparent")
        actions_bar.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkButton(
            actions_bar, text="✏️ Edit Selected Book", height=38,
            fg_color="#2563eb", hover_color="#1d4ed8",
            command=self._edit_book_dialog
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions_bar, text="🗑️ Delete Book", height=38,
            fg_color="#dc2626", hover_color="#b91c1c",
            command=self._delete_book
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions_bar, text="🔄 Quick Issue Selected", height=38,
            fg_color="#059669", hover_color="#047857",
            command=self._quick_issue
        ).pack(side="left")

    def _sort_by(self, col):
        if self.sort_column == col:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_column = col
            self.sort_descending = False
        self.load_data()

    def load_data(self):
        query = self.search_entry.get().strip()
        books = self.db.get_all_books(search_query=query, search_field="All")

        # Sort in memory
        def sort_key(b):
            val = b[self.sort_column]
            if val is None:
                return ""
            if isinstance(val, str):
                return val.lower()
            return val

        sorted_books = sorted(books, key=sort_key, reverse=self.sort_descending)

        for item in self.tree.get_children():
            self.tree.delete(item)

        for b in sorted_books:
            avail = b["available_copies"]
            status_text = "In Stock" if avail > 0 else "Out of Stock"
            tag = "available" if avail > 0 else "out_of_stock"

            self.tree.insert(
                "", "end",
                values=(
                    b["book_id"],
                    b["title"],
                    b["author"],
                    b["category"] or "—",
                    b["isbn"],
                    b["total_copies"],
                    b["available_copies"],
                    status_text
                ),
                tags=(tag,)
            )

        self.tree.tag_configure("available", foreground="#10b981")
        self.tree.tag_configure("out_of_stock", foreground="#ef4444")
        self.count_lbl.configure(text=f"Showing {len(sorted_books)} books")

    def refresh(self):
        self.load_data()

    def _get_selected_book_id(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select a book from the table first.")
            return None
        return self.tree.item(selected[0])["values"][0]

    def _delete_book(self):
        book_id = self._get_selected_book_id()
        if not book_id:
            return

        book = self.db.get_book(book_id)
        if not book:
            messagebox.showerror("Error", "Selected book not found.")
            return

        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to permanently delete the book:\n\n'{book['title']}' (ISBN: {book['isbn']})?\n\nThis action cannot be undone."
        )
        if not confirm:
            return

        try:
            self.db.delete_book(book_id)
            messagebox.showinfo("Success", f"Book '{book['title']}' was deleted successfully.")
            self.controller.refresh_all_views()
        except ValueError as e:
            messagebox.showerror("Cannot Delete", str(e))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete book: {e}")

    def _quick_issue(self):
        book_id = self._get_selected_book_id()
        if not book_id:
            return
        self.controller.views["IssueBookView"].preselect_book(book_id)
        self.controller.show_view("IssueBookView")

    def _edit_book_dialog(self):
        book_id = self._get_selected_book_id()
        if not book_id:
            return

        book = self.db.get_book(book_id)
        if not book:
            messagebox.showerror("Error", "Book not found.")
            return

        # Modal Edit Dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Edit Book #{book_id}")
        dialog.geometry("520x480")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        # Center dialog
        dialog.update_idletasks()
        x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() // 2) - 260
        y = self.winfo_toplevel().winfo_y() + (self.winfo_toplevel().winfo_height() // 2) - 240
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(
            dialog, text="✏️ Edit Book Details",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(anchor="w", padx=25, pady=(20, 15))

        f = ctk.CTkFrame(dialog, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=25)

        ctk.CTkLabel(f, text="Title *", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(2, 2))
        e_title = ctk.CTkEntry(f, height=36)
        e_title.insert(0, book["title"])
        e_title.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(f, text="Author *", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(2, 2))
        e_author = ctk.CTkEntry(f, height=36)
        e_author.insert(0, book["author"])
        e_author.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(f, text="Category", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(2, 2))
        e_cat = ctk.CTkEntry(f, height=36)
        e_cat.insert(0, book["category"] or "")
        e_cat.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(f, text="ISBN *", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(2, 2))
        e_isbn = ctk.CTkEntry(f, height=36)
        e_isbn.insert(0, book["isbn"])
        e_isbn.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(f, text="Total Copies *", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(2, 2))
        e_copies = ctk.CTkEntry(f, height=36)
        e_copies.insert(0, str(book["total_copies"]))
        e_copies.pack(fill="x", pady=(0, 15))

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=25, pady=(0, 20))

        def save_changes():
            t = e_title.get()
            a = e_author.get()
            c = e_cat.get()
            i = e_isbn.get()
            copies_str = e_copies.get().strip()

            if not copies_str.isdigit():
                messagebox.showerror("Error", "Total copies must be a valid number.", parent=dialog)
                return

            try:
                self.db.update_book(book_id, t, a, c, i, int(copies_str))
                messagebox.showinfo("Success", "Book updated successfully!", parent=dialog)
                dialog.destroy()
                self.controller.refresh_all_views()
            except ValueError as err:
                messagebox.showerror("Error", str(err), parent=dialog)

        ctk.CTkButton(
            btn_row, text="Save Changes", height=38,
            fg_color="#2563eb", hover_color="#1d4ed8",
            command=save_changes
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row, text="Cancel", height=38,
            fg_color=("gray75", "gray30"), hover_color=("gray65", "gray40"),
            command=dialog.destroy
        ).pack(side="left")


# ---------------------------------------------------------------------------
# 4. Register Member View
# ---------------------------------------------------------------------------
class RegisterMemberView(BaseView):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        card = ctk.CTkFrame(self, corner_radius=14)
        card.pack(fill="both", expand=True, padx=40, pady=30)

        # Header
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=35, pady=(30, 20))

        ctk.CTkLabel(
            head, text="👤 Register New Member",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            head,
            text="Add a new library patron. Membership date is automatically set to today.",
            font=ctk.CTkFont(size=13),
            text_color=("gray40", "gray70")
        ).pack(anchor="w", pady=(4, 0))

        # Form layout
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=35, pady=10)
        form.grid_columnconfigure((0, 1), weight=1)

        # Full Name
        ctk.CTkLabel(form, text="Full Name *", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(5, 3))
        self.entry_name = ctk.CTkEntry(form, placeholder_text="e.g. John Doe", height=42, font=ctk.CTkFont(size=14))
        self.entry_name.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 16))

        # Contact & Email
        ctk.CTkLabel(form, text="Contact / Phone *", font=ctk.CTkFont(size=14, weight="bold")).grid(row=2, column=0, sticky="w", pady=(5, 3), padx=(0, 10))
        self.entry_contact = ctk.CTkEntry(form, placeholder_text="e.g. +91 9876543210", height=42, font=ctk.CTkFont(size=14))
        self.entry_contact.grid(row=3, column=0, sticky="ew", pady=(0, 16), padx=(0, 10))

        ctk.CTkLabel(form, text="Email Address *", font=ctk.CTkFont(size=14, weight="bold")).grid(row=2, column=1, sticky="w", pady=(5, 3), padx=(10, 0))
        self.entry_email = ctk.CTkEntry(form, placeholder_text="e.g. john.doe@example.com", height=42, font=ctk.CTkFont(size=14))
        self.entry_email.grid(row=3, column=1, sticky="ew", pady=(0, 16), padx=(10, 0))

        # Address
        ctk.CTkLabel(form, text="Physical Address", font=ctk.CTkFont(size=14, weight="bold")).grid(row=4, column=0, columnspan=2, sticky="w", pady=(5, 3))
        self.entry_address = ctk.CTkEntry(form, placeholder_text="e.g. Apt 4B, Sunflower Apts, Main Street", height=42, font=ctk.CTkFont(size=14))
        self.entry_address.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 16))

        # Membership Date (Auto-filled Readonly)
        ctk.CTkLabel(form, text="Membership Registration Date", font=ctk.CTkFont(size=14, weight="bold")).grid(row=6, column=0, sticky="w", pady=(5, 3), padx=(0, 10))
        self.entry_date = ctk.CTkEntry(form, height=42, font=ctk.CTkFont(size=14))
        self.entry_date.insert(0, date.today().isoformat())
        self.entry_date.configure(state="readonly")
        self.entry_date.grid(row=7, column=0, sticky="ew", pady=(0, 16), padx=(0, 10))

        # Buttons
        btn_box = ctk.CTkFrame(card, fg_color="transparent")
        btn_box.pack(fill="x", padx=35, pady=(20, 35))

        self.btn_save = ctk.CTkButton(
            btn_box,
            text="💾 Register Member",
            height=46,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#0d9488",
            hover_color="#0f766e",
            command=self._save_member
        )
        self.btn_save.pack(side="left", padx=(0, 15))

        self.btn_clear = ctk.CTkButton(
            btn_box,
            text="🧹 Clear Fields",
            height=46,
            width=120,
            font=ctk.CTkFont(size=14),
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            text_color=("black", "white"),
            command=self.clear_form
        )
        self.btn_clear.pack(side="left")

    def _save_member(self):
        name = self.entry_name.get()
        contact = self.entry_contact.get()
        email = self.entry_email.get()
        address = self.entry_address.get()

        try:
            member_id = self.db.add_member(name, contact, email, address)
            messagebox.showinfo("Member Registered", f"Member registered successfully!\n\nMember ID: #{member_id}\nName: {name}\nEmail: {email}")
            self.clear_form()
            self.controller.refresh_all_views()
        except ValueError as e:
            messagebox.showerror("Registration Error", str(e))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to register member: {e}")

    def clear_form(self):
        self.entry_name.delete(0, "end")
        self.entry_contact.delete(0, "end")
        self.entry_email.delete(0, "end")
        self.entry_address.delete(0, "end")


# ---------------------------------------------------------------------------
# 5. View / Manage Members View
# ---------------------------------------------------------------------------
class ViewMembersView(BaseView):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        card = ctk.CTkFrame(self, corner_radius=14)
        card.pack(fill="both", expand=True, padx=25, pady=25)

        # Header
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 15))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box, text="👥 Member Directory",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold")
        ).pack(anchor="w")

        self.count_lbl = ctk.CTkLabel(
            title_box, text="Showing 0 members", font=ctk.CTkFont(size=13),
            text_color=("gray40", "gray70")
        )
        self.count_lbl.pack(anchor="w")

        # Search Bar
        search_box = ctk.CTkFrame(header, fg_color="transparent")
        search_box.pack(side="right")

        self.search_entry = ctk.CTkEntry(
            search_box, placeholder_text="🔍 Filter by name, email, or contact...",
            width=280, height=36
        )
        self.search_entry.pack(side="left", padx=(0, 8))
        self.search_entry.bind("<KeyRelease>", lambda event: self.load_data())

        ctk.CTkButton(
            search_box, text="Refresh", width=80, height=36,
            command=self.load_data
        ).pack(side="left")

        # Table
        table_frame = ctk.CTkFrame(card, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        columns = ("member_id", "name", "contact", "email", "address", "joined", "active_loans")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("member_id", text="ID")
        self.tree.heading("name", text="Full Name")
        self.tree.heading("contact", text="Contact")
        self.tree.heading("email", text="Email Address")
        self.tree.heading("address", text="Address")
        self.tree.heading("joined", text="Joined Date")
        self.tree.heading("active_loans", text="Active Loans (Max 3)")

        self.tree.column("member_id", width=55, anchor="center")
        self.tree.column("name", width=180, anchor="w")
        self.tree.column("contact", width=130, anchor="center")
        self.tree.column("email", width=200, anchor="w")
        self.tree.column("address", width=180, anchor="w")
        self.tree.column("joined", width=110, anchor="center")
        self.tree.column("active_loans", width=130, anchor="center")

        tree_scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set)

        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll_y.pack(side="right", fill="y")

        # Actions Bar
        actions_bar = ctk.CTkFrame(card, fg_color="transparent")
        actions_bar.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkButton(
            actions_bar, text="✏️ Edit Member", height=38,
            fg_color="#0d9488", hover_color="#0f766e",
            command=self._edit_member_dialog
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions_bar, text="🗑️ Delete Member", height=38,
            fg_color="#dc2626", hover_color="#b91c1c",
            command=self._delete_member
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions_bar, text="🔄 Issue Book to Member", height=38,
            fg_color="#2563eb", hover_color="#1d4ed8",
            command=self._quick_issue_to_member
        ).pack(side="left")

    def load_data(self):
        query = self.search_entry.get().strip()
        members = self.db.get_all_members(search_query=query)

        for item in self.tree.get_children():
            self.tree.delete(item)

        for m in members:
            loans = m["active_loans"]
            loan_badge = f"{loans} / {MAX_ACTIVE_LOANS}"
            tag = "max_loans" if loans >= MAX_ACTIVE_LOANS else ("has_loans" if loans > 0 else "zero_loans")

            self.tree.insert(
                "", "end",
                values=(
                    m["member_id"],
                    m["name"],
                    m["contact"],
                    m["email"],
                    m["address"] or "—",
                    m["membership_date"],
                    loan_badge
                ),
                tags=(tag,)
            )

        self.tree.tag_configure("max_loans", foreground="#ef4444")
        self.tree.tag_configure("has_loans", foreground="#f59e0b")
        self.tree.tag_configure("zero_loans", foreground="#10b981")
        self.count_lbl.configure(text=f"Showing {len(members)} registered members")

    def refresh(self):
        self.load_data()

    def _get_selected_member_id(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select a member from the table first.")
            return None
        return self.tree.item(selected[0])["values"][0]

    def _delete_member(self):
        member_id = self._get_selected_member_id()
        if not member_id:
            return

        member = self.db.get_member(member_id)
        if not member:
            messagebox.showerror("Error", "Member not found.")
            return

        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to permanently delete member:\n\n'{member['name']}' ({member['email']})?\n\nThis cannot be undone."
        )
        if not confirm:
            return

        try:
            self.db.delete_member(member_id)
            messagebox.showinfo("Success", f"Member '{member['name']}' was removed.")
            self.controller.refresh_all_views()
        except ValueError as e:
            messagebox.showerror("Cannot Delete", str(e))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete member: {e}")

    def _quick_issue_to_member(self):
        member_id = self._get_selected_member_id()
        if not member_id:
            return
        self.controller.views["IssueBookView"].preselect_member(member_id)
        self.controller.show_view("IssueBookView")

    def _edit_member_dialog(self):
        member_id = self._get_selected_member_id()
        if not member_id:
            return

        member = self.db.get_member(member_id)
        if not member:
            messagebox.showerror("Error", "Member not found.")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Edit Member #{member_id}")
        dialog.geometry("480x420")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        dialog.update_idletasks()
        x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() // 2) - 240
        y = self.winfo_toplevel().winfo_height() // 2 - 210 + self.winfo_toplevel().winfo_y()
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(
            dialog, text="✏️ Edit Member Information",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(anchor="w", padx=25, pady=(20, 15))

        f = ctk.CTkFrame(dialog, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=25)

        ctk.CTkLabel(f, text="Full Name *", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(2, 2))
        e_name = ctk.CTkEntry(f, height=36)
        e_name.insert(0, member["name"])
        e_name.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(f, text="Contact / Phone *", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(2, 2))
        e_contact = ctk.CTkEntry(f, height=36)
        e_contact.insert(0, member["contact"])
        e_contact.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(f, text="Email Address *", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(2, 2))
        e_email = ctk.CTkEntry(f, height=36)
        e_email.insert(0, member["email"])
        e_email.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(f, text="Address", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(2, 2))
        e_addr = ctk.CTkEntry(f, height=36)
        e_addr.insert(0, member["address"] or "")
        e_addr.pack(fill="x", pady=(0, 15))

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=25, pady=(0, 20))

        def save_changes():
            n = e_name.get()
            c = e_contact.get()
            em = e_email.get()
            ad = e_addr.get()

            try:
                self.db.update_member(member_id, n, c, em, ad)
                messagebox.showinfo("Success", "Member details updated successfully!", parent=dialog)
                dialog.destroy()
                self.controller.refresh_all_views()
            except ValueError as err:
                messagebox.showerror("Error", str(err), parent=dialog)

        ctk.CTkButton(
            btn_row, text="Save Changes", height=38,
            fg_color="#0d9488", hover_color="#0f766e",
            command=save_changes
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row, text="Cancel", height=38,
            fg_color=("gray75", "gray30"), hover_color=("gray65", "gray40"),
            command=dialog.destroy
        ).pack(side="left")


# ---------------------------------------------------------------------------
# 6. Issue Book View
# ---------------------------------------------------------------------------
class IssueBookView(BaseView):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        self.members_map = {}  # "ID - Name": id
        self.books_map = {}    # "ID - Title": id

        card = ctk.CTkFrame(self, corner_radius=14)
        card.pack(fill="both", expand=True, padx=40, pady=25)

        # Header
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=35, pady=(25, 15))

        ctk.CTkLabel(
            head, text="🔄 Issue Book to Member",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            head,
            text=f"Select a registered member and an available book. Maximum {MAX_ACTIVE_LOANS} active books per member. Loan period is {LOAN_PERIOD_DAYS} days.",
            font=ctk.CTkFont(size=13),
            text_color=("gray40", "gray70")
        ).pack(anchor="w", pady=(4, 0))

        # Main layout: 2 side-by-side selection panels + Details summary
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=35, pady=10)
        content.grid_columnconfigure((0, 1), weight=1)

        # Left: Member Selection
        mem_card = ctk.CTkFrame(content, corner_radius=10)
        mem_card.grid(row=0, column=0, padx=(0, 12), sticky="nsew", ipady=10)

        ctk.CTkLabel(
            mem_card, text="1. Select Member",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=20, pady=(15, 5))

        self.combo_member = ctk.CTkComboBox(
            mem_card, values=["Loading members..."], height=40,
            command=self._on_member_selected
        )
        self.combo_member.pack(fill="x", padx=20, pady=(5, 12))

        # Member Status Preview Card
        self.mem_preview = ctk.CTkFrame(mem_card, fg_color=("gray85", "gray20"), corner_radius=8)
        self.mem_preview.pack(fill="x", padx=20, pady=(0, 15), ipady=8)

        self.mem_info_lbl = ctk.CTkLabel(
            self.mem_preview,
            text="No member selected\nChoose a member to view eligibility status",
            justify="left",
            font=ctk.CTkFont(size=13)
        )
        self.mem_info_lbl.pack(padx=14, pady=10, anchor="w")

        # Right: Book Selection
        bk_card = ctk.CTkFrame(content, corner_radius=10)
        bk_card.grid(row=0, column=1, padx=(12, 0), sticky="nsew", ipady=10)

        ctk.CTkLabel(
            bk_card, text="2. Select Book",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=20, pady=(15, 5))

        self.combo_book = ctk.CTkComboBox(
            bk_card, values=["Loading books..."], height=40,
            command=self._on_book_selected
        )
        self.combo_book.pack(fill="x", padx=20, pady=(5, 12))

        # Book Status Preview Card
        self.bk_preview = ctk.CTkFrame(bk_card, fg_color=("gray85", "gray20"), corner_radius=8)
        self.bk_preview.pack(fill="x", padx=20, pady=(0, 15), ipady=8)

        self.bk_info_lbl = ctk.CTkLabel(
            self.bk_preview,
            text="No book selected\nChoose a book to check available stock",
            justify="left",
            font=ctk.CTkFont(size=13)
        )
        self.bk_info_lbl.pack(padx=14, pady=10, anchor="w")

        # Bottom Loan Schedule & Confirmation
        sched_card = ctk.CTkFrame(card, corner_radius=10)
        sched_card.pack(fill="x", padx=35, pady=(15, 25), ipady=8)

        sched_inner = ctk.CTkFrame(sched_card, fg_color="transparent")
        sched_inner.pack(fill="x", padx=20, pady=10)
        sched_inner.grid_columnconfigure((0, 1, 2), weight=1)

        today_dt = date.today()
        due_dt = today_dt + timedelta(days=LOAN_PERIOD_DAYS)

        # Issue Date Box
        box1 = ctk.CTkFrame(sched_inner, fg_color="transparent")
        box1.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(box1, text="Issue Date:", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(box1, text=today_dt.strftime("%d %b %Y (Today)"), font=ctk.CTkFont(size=14), text_color="#2563eb").pack(anchor="w")

        # Due Date Box
        box2 = ctk.CTkFrame(sched_inner, fg_color="transparent")
        box2.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(box2, text="Expected Due Date:", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(box2, text=due_dt.strftime("%d %b %Y (+14 Days)"), font=ctk.CTkFont(size=14), text_color="#059669").pack(anchor="w")

        # Fine Policy Box
        box3 = ctk.CTkFrame(sched_inner, fg_color="transparent")
        box3.grid(row=0, column=2, sticky="w")
        ctk.CTkLabel(box3, text="Overdue Fine Rate:", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(box3, text=f"₹{FINE_PER_DAY:.2f} per late day", font=ctk.CTkFont(size=14), text_color="#d97706").pack(anchor="w")

        # Submit Button
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=35, pady=(0, 25))

        self.btn_issue = ctk.CTkButton(
            btn_frame,
            text="🚀 Confirm & Issue Book",
            height=46,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=self._issue_book
        )
        self.btn_issue.pack(side="left", padx=(0, 15))

    def refresh(self):
        # Reload dropdown items
        members = self.db.get_all_members()
        self.members_map = {f"#{m['member_id']} - {m['name']} ({m['email']})": m['member_id'] for m in members}
        mem_vals = list(self.members_map.keys()) if self.members_map else ["No members registered"]
        self.combo_member.configure(values=mem_vals)
        if mem_vals and self.combo_member.get() not in self.members_map:
            self.combo_member.set(mem_vals[0])
            self._on_member_selected(mem_vals[0])

        books = self.db.get_all_books()
        self.books_map = {f"#{b['book_id']} - {b['title']} (Avail: {b['available_copies']}/{b['total_copies']})": b['book_id'] for b in books}
        bk_vals = list(self.books_map.keys()) if self.books_map else ["No books in catalog"]
        self.combo_book.configure(values=bk_vals)
        if bk_vals and self.combo_book.get() not in self.books_map:
            self.combo_book.set(bk_vals[0])
            self._on_book_selected(bk_vals[0])

    def preselect_book(self, book_id):
        self.refresh()
        for k, v in self.books_map.items():
            if v == book_id:
                self.combo_book.set(k)
                self._on_book_selected(k)
                break

    def preselect_member(self, member_id):
        self.refresh()
        for k, v in self.members_map.items():
            if v == member_id:
                self.combo_member.set(k)
                self._on_member_selected(k)
                break

    def _on_member_selected(self, choice):
        member_id = self.members_map.get(choice)
        if not member_id:
            return
        m = self.db.get_member(member_id)
        if not m:
            return
        active_loans = self.db.get_member_active_loans_count(member_id)
        status_msg = "⚠️ Limit Reached" if active_loans >= MAX_ACTIVE_LOANS else "✅ Eligible to Borrow"

        self.mem_info_lbl.configure(
            text=f"Patron: {m['name']}\nEmail: {m['email']}\nPhone: {m['contact']}\nActive Loans: {active_loans} / {MAX_ACTIVE_LOANS} ({status_msg})"
        )

    def _on_book_selected(self, choice):
        book_id = self.books_map.get(choice)
        if not book_id:
            return
        b = self.db.get_book(book_id)
        if not b:
            return
        avail = b["available_copies"]
        status_msg = "✅ Available in Stock" if avail > 0 else "❌ Out of Stock"

        self.bk_info_lbl.configure(
            text=f"Title: {b['title']}\nAuthor: {b['author']}\nISBN: {b['isbn']}\nAvailable: {avail} of {b['total_copies']} copies ({status_msg})"
        )

    def _issue_book(self):
        member_key = self.combo_member.get()
        book_key = self.combo_book.get()

        member_id = self.members_map.get(member_key)
        book_id = self.books_map.get(book_key)

        if not member_id or not book_id:
            messagebox.showerror("Error", "Please select a valid member and book from the options.")
            return

        try:
            result = self.db.issue_book(member_id, book_id)
            messagebox.showinfo(
                "Book Issued Successfully!",
                f"Transaction ID: #{result['transaction_id']}\n\n"
                f"Borrower: {result['member_name']}\n"
                f"Book: {result['book_title']}\n"
                f"Issue Date: {result['issue_date']}\n"
                f"Due Date: {result['due_date']}\n\n"
                f"Please ensure the book is returned on or before the due date to avoid fines."
            )
            self.controller.refresh_all_views()
        except ValueError as e:
            messagebox.showerror("Validation Error", str(e))
        except Exception as e:
            messagebox.showerror("System Error", f"Failed to issue book: {e}")


# ---------------------------------------------------------------------------
# 7. Return Book View
# ---------------------------------------------------------------------------
class ReturnBookView(BaseView):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        card = ctk.CTkFrame(self, corner_radius=14)
        card.pack(fill="both", expand=True, padx=25, pady=25)

        # Header
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 15))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box, text="📥 Return Book & Calculate Fines",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text=f"Select an active loan below or enter Transaction ID. Overdue fine is ₹{FINE_PER_DAY:.2f} per late day.",
            font=ctk.CTkFont(size=13),
            text_color=("gray40", "gray70")
        ).pack(anchor="w", pady=(2, 0))

        # Direct Return Bar
        search_bar = ctk.CTkFrame(header, fg_color="transparent")
        search_bar.pack(side="right")

        ctk.CTkLabel(search_bar, text="Tx ID:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 6))
        self.entry_tx_id = ctk.CTkEntry(search_bar, placeholder_text="e.g. 2", width=90, height=36)
        self.entry_tx_id.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            search_bar, text="Return by ID", width=110, height=36,
            fg_color="#059669", hover_color="#047857",
            command=self._return_by_entry
        ).pack(side="left")

        # Active Loans Table
        table_frame = ctk.CTkFrame(card, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        columns = ("tx_id", "member", "book", "issue_date", "due_date", "days_remaining", "estimated_fine")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("tx_id", text="Tx ID")
        self.tree.heading("member", text="Borrower Member")
        self.tree.heading("book", text="Book Title")
        self.tree.heading("issue_date", text="Issue Date")
        self.tree.heading("due_date", text="Due Date")
        self.tree.heading("days_remaining", text="Loan Status")
        self.tree.heading("estimated_fine", text="Accrued Fine (₹)")

        self.tree.column("tx_id", width=65, anchor="center")
        self.tree.column("member", width=190, anchor="w")
        self.tree.column("book", width=240, anchor="w")
        self.tree.column("issue_date", width=110, anchor="center")
        self.tree.column("due_date", width=110, anchor="center")
        self.tree.column("days_remaining", width=140, anchor="center")
        self.tree.column("estimated_fine", width=120, anchor="center")

        tree_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self._on_row_selected)

        # Bottom Selected Loan Summary & Action
        bottom_frame = ctk.CTkFrame(card, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=20, pady=(0, 20))

        self.summary_card = ctk.CTkFrame(bottom_frame, fg_color=("gray85", "gray20"), corner_radius=10)
        self.summary_card.pack(side="left", fill="x", expand=True, padx=(0, 15), ipady=6)

        self.summary_lbl = ctk.CTkLabel(
            self.summary_card,
            text="Select an active transaction from the table above to preview return calculations.",
            font=ctk.CTkFont(size=13),
            justify="left"
        )
        self.summary_lbl.pack(padx=16, pady=8, anchor="w")

        self.btn_process_return = ctk.CTkButton(
            bottom_frame,
            text="📥 Process Return for Selected",
            height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            command=self._return_selected
        )
        self.btn_process_return.pack(side="right")

    def load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        rows = self.db.get_active_transactions()
        today = date.today()

        for r in rows:
            due_dt = date.fromisoformat(r["due_date"])
            diff = (due_dt - today).days

            if diff < 0:
                overdue_days = abs(diff)
                status_text = f"⚠️ {overdue_days} day(s) OVERDUE"
                fine = overdue_days * FINE_PER_DAY
                tag = "overdue"
            elif diff == 0:
                status_text = "⏰ Due Today!"
                fine = 0.0
                tag = "due_today"
            else:
                status_text = f"✅ {diff} days left"
                fine = 0.0
                tag = "on_time"

            self.tree.insert(
                "", "end",
                values=(
                    r["transaction_id"],
                    r["member_name"],
                    r["book_title"],
                    r["issue_date"],
                    r["due_date"],
                    status_text,
                    f"₹{fine:.2f}"
                ),
                tags=(tag,)
            )

        self.tree.tag_configure("overdue", foreground="#ef4444")
        self.tree.tag_configure("due_today", foreground="#f59e0b")
        self.tree.tag_configure("on_time", foreground="#10b981")

    def refresh(self):
        self.load_data()
        self.summary_lbl.configure(text="Select an active transaction from the table above to preview return calculations.")
        self.entry_tx_id.delete(0, "end")

    def _on_row_selected(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        vals = self.tree.item(selected[0])["values"]
        tx_id, member, book, _, due_str, status_str, fine_str = vals
        self.entry_tx_id.delete(0, "end")
        self.entry_tx_id.insert(0, str(tx_id))

        self.summary_lbl.configure(
            text=f"Transaction #{tx_id} Selected | Borrower: {member} | Book: {book}\nStatus: {status_str} | Estimated Fine: {fine_str}"
        )

    def _process_return_by_id(self, tx_id):
        try:
            res = self.db.return_book(tx_id)
            if res["overdue_days"] > 0:
                msg = (
                    f"Book returned successfully!\n\n"
                    f"Transaction ID: #{res['transaction_id']}\n"
                    f"Book: {res['book_title']}\n"
                    f"Borrower: {res['member_name']}\n"
                    f"Due Date: {res['due_date']}\n"
                    f"Return Date: {res['return_date']}\n\n"
                    f"⚠️ OVERDUE by {res['overdue_days']} day(s)!\n"
                    f"Fine Collected: ₹{res['fine']:.2f}"
                )
            else:
                msg = (
                    f"Book returned on time!\n\n"
                    f"Transaction ID: #{res['transaction_id']}\n"
                    f"Book: {res['book_title']}\n"
                    f"Borrower: {res['member_name']}\n"
                    f"Return Date: {res['return_date']}\n\n"
                    f"Fine: ₹0.00 (No late fee applied)"
                )
            messagebox.showinfo("Return Summary", msg)
            self.controller.refresh_all_views()
        except ValueError as e:
            messagebox.showerror("Return Error", str(e))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to return book: {e}")

    def _return_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select a loan record from the table first.")
            return
        tx_id = self.tree.item(selected[0])["values"][0]
        self._process_return_by_id(int(tx_id))

    def _return_by_entry(self):
        tx_str = self.entry_tx_id.get().strip()
        if not tx_str or not tx_str.isdigit():
            messagebox.showerror("Invalid ID", "Please enter a valid numeric Transaction ID.")
            return
        self._process_return_by_id(int(tx_str))


# ---------------------------------------------------------------------------
# 8. Search Books View
# ---------------------------------------------------------------------------
class SearchBookView(BaseView):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        card = ctk.CTkFrame(self, corner_radius=14)
        card.pack(fill="both", expand=True, padx=25, pady=25)

        # Header
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=25, pady=(25, 15))

        ctk.CTkLabel(
            header, text="🔍 Search Library Catalog",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            header,
            text="Perform instant partial and case-insensitive searches across titles, authors, categories, and ISBNs.",
            font=ctk.CTkFont(size=13),
            text_color=("gray40", "gray70")
        ).pack(anchor="w", pady=(3, 0))

        # Search Controls Card
        ctrl_card = ctk.CTkFrame(card, fg_color=("gray85", "gray20"), corner_radius=10)
        ctrl_card.pack(fill="x", padx=25, pady=(0, 15), ipady=8)

        ctrl_inner = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        ctrl_inner.pack(fill="x", padx=16, pady=8)

        ctk.CTkLabel(ctrl_inner, text="Search Field:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 8))

        self.combo_filter = ctk.CTkComboBox(
            ctrl_inner,
            values=["All", "Title", "Author", "ISBN", "Category"],
            width=120, height=38
        )
        self.combo_filter.set("All")
        self.combo_filter.pack(side="left", padx=(0, 12))

        self.search_entry = ctk.CTkEntry(
            ctrl_inner,
            placeholder_text="Type search keywords here...",
            height=38
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", lambda event: self.do_search())
        self.search_entry.bind("<Return>", lambda event: self.do_search())

        ctk.CTkButton(
            ctrl_inner, text="🔍 Search", width=90, height=38,
            command=self.do_search
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            ctrl_inner, text="Clear", width=70, height=38,
            fg_color=("gray70", "gray35"), hover_color=("gray60", "gray45"),
            command=self.clear_search
        ).pack(side="left")

        # Results Table
        table_frame = ctk.CTkFrame(card, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=25, pady=(0, 15))

        columns = ("book_id", "title", "author", "category", "isbn", "available", "total", "status")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("book_id", text="ID")
        self.tree.heading("title", text="Title")
        self.tree.heading("author", text="Author")
        self.tree.heading("category", text="Category")
        self.tree.heading("isbn", text="ISBN")
        self.tree.heading("available", text="Available")
        self.tree.heading("total", text="Total")
        self.tree.heading("status", text="Availability")

        self.tree.column("book_id", width=50, anchor="center")
        self.tree.column("title", width=250, anchor="w")
        self.tree.column("author", width=170, anchor="w")
        self.tree.column("category", width=120, anchor="w")
        self.tree.column("isbn", width=120, anchor="center")
        self.tree.column("available", width=80, anchor="center")
        self.tree.column("total", width=70, anchor="center")
        self.tree.column("status", width=120, anchor="center")

        tree_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        # Results Count & Actions
        bot_bar = ctk.CTkFrame(card, fg_color="transparent")
        bot_bar.pack(fill="x", padx=25, pady=(0, 20))

        self.results_lbl = ctk.CTkLabel(bot_bar, text="Showing all books", font=ctk.CTkFont(size=13))
        self.results_lbl.pack(side="left")

        ctk.CTkButton(
            bot_bar, text="🔄 Issue Selected Book", height=38,
            fg_color="#2563eb", hover_color="#1d4ed8",
            command=self._issue_selected
        ).pack(side="right")

    def do_search(self):
        query = self.search_entry.get().strip()
        field = self.combo_filter.get()
        books = self.db.get_all_books(search_query=query, search_field=field)

        for item in self.tree.get_children():
            self.tree.delete(item)

        for b in books:
            avail = b["available_copies"]
            status_text = f"✅ Available ({avail})" if avail > 0 else "❌ Out of Stock"
            tag = "avail" if avail > 0 else "unavail"

            self.tree.insert(
                "", "end",
                values=(
                    b["book_id"],
                    b["title"],
                    b["author"],
                    b["category"] or "—",
                    b["isbn"],
                    b["available_copies"],
                    b["total_copies"],
                    status_text
                ),
                tags=(tag,)
            )

        self.tree.tag_configure("avail", foreground="#10b981")
        self.tree.tag_configure("unavail", foreground="#ef4444")

        if query:
            self.results_lbl.configure(text=f"Found {len(books)} match(es) for '{query}' in {field}")
        else:
            self.results_lbl.configure(text=f"Showing all {len(books)} books in catalog")

    def clear_search(self):
        self.search_entry.delete(0, "end")
        self.combo_filter.set("All")
        self.do_search()

    def refresh(self):
        self.do_search()

    def _issue_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select a book from search results first.")
            return
        book_id = self.tree.item(selected[0])["values"][0]
        self.controller.views["IssueBookView"].preselect_book(book_id)
        self.controller.show_view("IssueBookView")


# ---------------------------------------------------------------------------
# Main Application Window & Navigation Controller
# ---------------------------------------------------------------------------
class LibraryManagementApp(ctk.CTk):
    """Primary application window and navigation controller."""

    def __init__(self):
        super().__init__()

        self.title(APP_TITLE)
        self.geometry("1180x720")
        self.minsize(1050, 640)

        # Center window on screen
        self._center_window(1180, 720)

        # Database initialization
        self.db = DatabaseManager()

        # Appearance mode tracker
        self.current_theme = "Dark"
        style_treeview(self.current_theme)

        # Build Main UI Shell
        self._build_ui()

    def _center_window(self, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2) - 30
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    def _build_ui(self):
        # Master grid: Left sidebar (fixed width) + Right content area (flexible)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ---------------- Left Sidebar ----------------
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # App Brand Header
        brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=18, pady=(24, 20))

        logo_lbl = ctk.CTkLabel(
            brand_frame, text="🏛️ LMS Pro",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold")
        )
        logo_lbl.pack(anchor="w")

        sub_logo = ctk.CTkLabel(
            brand_frame, text="Library Management System",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70")
        )
        sub_logo.pack(anchor="w")

        # Sidebar Separator
        sep1 = ctk.CTkFrame(self.sidebar, height=2, fg_color=("gray75", "gray25"))
        sep1.pack(fill="x", padx=18, pady=(0, 14))

        # Navigation Buttons Container
        self.nav_buttons = {}
        nav_items = [
            ("DashboardView", "📊  Dashboard"),
            ("AddBookView", "➕  Add Book"),
            ("ViewBooksView", "📚  Manage Books"),
            ("RegisterMemberView", "👤  Register Member"),
            ("ViewMembersView", "👥  Manage Members"),
            ("IssueBookView", "🔄  Issue Book"),
            ("ReturnBookView", "📥  Return Book"),
            ("SearchBookView", "🔍  Search Books"),
        ]

        for view_name, label in nav_items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                anchor="w",
                height=42,
                font=ctk.CTkFont(family="Segoe UI", size=14, weight="normal"),
                fg_color="transparent",
                text_color=("gray20", "gray85"),
                hover_color=("gray85", "gray25"),
                corner_radius=8,
                command=lambda v=view_name: self.show_view(v)
            )
            btn.pack(fill="x", padx=14, pady=3)
            self.nav_buttons[view_name] = btn

        # Bottom Section (Theme Toggle & System Info)
        bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", padx=18, pady=20)

        sep2 = ctk.CTkFrame(bottom_frame, height=2, fg_color=("gray75", "gray25"))
        sep2.pack(fill="x", pady=(0, 14))

        theme_lbl = ctk.CTkLabel(
            bottom_frame, text="Appearance Mode",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        theme_lbl.pack(anchor="w", pady=(0, 6))

        self.theme_switch = ctk.CTkSwitch(
            bottom_frame,
            text="Dark Mode",
            command=self._toggle_theme,
            font=ctk.CTkFont(size=13)
        )
        self.theme_switch.select()
        self.theme_switch.pack(anchor="w")

        # ---------------- Right Main Display Area ----------------
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew")
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        # Initialize View Registry
        self.views = {}
        for ViewClass in (DashboardView, AddBookView, ViewBooksView, RegisterMemberView,
                          ViewMembersView, IssueBookView, ReturnBookView, SearchBookView):
            v_name = ViewClass.__name__
            view_instance = ViewClass(self.main_container, self)
            view_instance.grid(row=0, column=0, sticky="nsew")
            self.views[v_name] = view_instance

        # Show initial Dashboard
        self.show_view("DashboardView")

    def show_view(self, view_name):
        """Switches the active visible view frame and updates sidebar active state."""
        target_view = self.views.get(view_name)
        if not target_view:
            return

        target_view.tkraise()
        target_view.refresh()

        # Update sidebar button styles
        for name, btn in self.nav_buttons.items():
            if name == view_name:
                btn.configure(
                    fg_color=("#3b82f6", "#2563eb"),
                    text_color="#ffffff",
                    font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=("gray20", "gray85"),
                    font=ctk.CTkFont(family="Segoe UI", size=14, weight="normal")
                )

    def refresh_all_views(self):
        """Refreshes cached data across active views."""
        for view in self.views.values():
            view.refresh()

    def _toggle_theme(self):
        if self.theme_switch.get() == 1:
            self.current_theme = "Dark"
            ctk.set_appearance_mode("Dark")
            self.theme_switch.configure(text="Dark Mode")
        else:
            self.current_theme = "Light"
            ctk.set_appearance_mode("Light")
            self.theme_switch.configure(text="Light Mode")

        style_treeview(self.current_theme)
        self.refresh_all_views()


# ---------------------------------------------------------------------------
# Application Entry Point
# ---------------------------------------------------------------------------
def main():
    app = LibraryManagementApp()
    app.mainloop()


if __name__ == "__main__":
    main()
