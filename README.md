# 🏛️ Library Management System (LMS Pro)

A modern, attractive desktop application built with **Python 3**, **CustomTkinter** for a polished flat UI with light/dark theme toggle, and **SQLite3** for persistent local storage.

---

## 🌟 Key Features

### 📊 1. Real-Time Dashboard
- **4 Live KPI Cards**: Total Book Titles & Copies, Registered Members, Active Loans, and Overdue Books with accumulated fines.
- **Quick Action Buttons**: Fast shortcuts to Issue, Return, Add Book, and Register Member.
- **Recent Activity Table**: View the latest transactions with color-coded status badges (`Issued`, `Returned`, `Overdue`).

### 📚 2. Book Management
- **Add Book**: Form with Title, Author, Category/Genre, unique ISBN, and Total Copies. Automatically sets `available_copies = total_copies`.
- **Inventory Table**: Sortable columns (click header to toggle Ascending/Descending), live filter search bar.
- **Edit Book**: Modal dialog to modify book details and copy quantities while preserving loan consistency.
- **Delete Protection**: Confirm dialog; deletes are strictly prevented if there are active loans for the book.

### 👤 3. Member Management
- **Register Member**: Full Name, Contact, Email, Address, and auto-filled registration date.
- **Email Validation**: Checks standard email format via regex and prevents duplicate emails.
- **Directory Table**: Shows all registered members and their active loans count (`x / 3`).
- **Edit Member**: Update contact, address, or email with uniqueness check.
- **Delete Protection**: Prevents deleting members who currently have unreturned books.

### 🔄 4. Book Issue
- **Interactive Selectors**: Member and Book dropdowns with live status preview cards.
- **Validation Guards**:
  - Member and Book existence checks.
  - Out of stock prevention: blocks borrowing if `available_copies <= 0`.
  - Max borrowing limit: members cannot borrow more than 3 active books.
- **Automated Scheduling**: Automatically calculates loan issue date (today) and due date (today + 14 days), decrements available copies by 1.

### 📥 5. Book Return & Fine Calculation
- **Active Loans Table**: Instant one-click selection of currently borrowed books with days remaining indicator.
- **Transaction ID Return**: Optional manual ID lookup bar.
- **Automated Fine Calculation**:
  - Automatically calculates overdue days = `today - due_date`.
  - Late fee rate: **₹5.00 per day overdue** (₹0 if returned on or before due date).
- **Return Summary**: Displays an alert with borrower name, return date, days overdue, and fine amount.
- **Inventory Restoration**: Automatically increments book's `available_copies` by 1.

### 🔍 6. Multi-Criteria Catalog Search
- Search bar with dropdown selector: **All**, **Title**, **Author**, **ISBN**, or **Category**.
- Instant live search matching as you type.
- Direct "Issue Selected Book" action.

### 🎨 7. Modern UI & Theme Switching
- Sleek CustomTkinter modern widgets with rounded corners and consistent typography.
- **Appearance Switcher**: Instant live toggle between **🌙 Dark Mode** and **☀️ Light Mode**.
- Custom-styled `Treeview` tables adapting colors, highlights, and headers to match the selected theme.

---

## 🛠️ Project Structure

```
d:/Library_Management_System/
├── main.py                     # Single-file complete desktop application
├── library.db                  # Local SQLite database (auto-generated on first run)
├── requirements.txt            # Python dependencies (customtkinter, pyinstaller, etc.)
├── test_app.py                 # Comprehensive automated unit & integration test suite
├── run.bat                     # Windows batch launcher (runs source python)
├── build_exe.py                # PyInstaller compilation script
├── build_exe.bat               # 1-click Windows batch script to compile .exe
├── dist/
│   └── LibraryManagementSystem.exe  # Standalone Windows executable (~11.5 MB)
├── vercel.json                 # Vercel deployment configuration
└── website/                    # Modern landing page for Vercel deployment
    ├── index.html              # Responsive product showcase & download landing page
    └── LibraryManagementSystem.exe  # Downloadable executable bundle
```

---

## 🖥️ Running the Application

### Option A: Run Pre-Compiled Standalone .EXE (No Python Needed)
Run directly from `dist/`:
```powershell
.\dist\LibraryManagementSystem.exe
```

### Option B: Run from Source via Batch Script
Double-click `run.bat` in the project root.

### Option C: Run via Python Terminal
```powershell
.venv\Scripts\python main.py
```

---

## 🔨 Rebuilding the Standalone .EXE

If you make modifications to `main.py` and want to generate a new standalone `.exe`:

```powershell
.venv\Scripts\python build_exe.py
```
Or double-click `build_exe.bat`. The resulting binary will be placed in `dist/LibraryManagementSystem.exe`.

---

## 🌐 Deploying the Landing Page & Download to Vercel

The project includes a ready-to-deploy showcase website in the `website/` folder with `vercel.json` configured.

### Method 1: Deploy via GitHub (Recommended)
1. Initialize git and push your repository to GitHub:
   ```bash
   git init
   git add .
   git commit -m "Initial commit of LMS Pro"
   git remote add origin https://github.com/YOUR_USERNAME/Library_Management_System.git
   git push -u origin main
   ```
2. Go to [vercel.com](https://vercel.com) and log in.
3. Click **Add New...** -> **Project**.
4. Import your `Library_Management_System` repository.
5. In the project settings, keep the defaults (the root `vercel.json` handles rewrites to `/website`).
6. Click **Deploy**!
   Your site will be live at `https://your-project.vercel.app` with instant download buttons for the `.exe`.

### Method 2: Deploy via Vercel CLI
If you have the Vercel CLI installed:
```powershell
# From the project directory:
vercel
```
Follow the interactive prompts to deploy directly from your local terminal.

---

## 🧪 Running Automated Tests

```powershell
.venv\Scripts\python -m unittest test_app.py
```

All 7 test suites will execute and validate:
1. `test_schema_and_initial_seed`
2. `test_add_book_and_duplicate_isbn`
3. `test_member_email_validation_and_duplicate`
4. `test_borrow_limit_enforcement` (max 3 books limit)
5. `test_out_of_stock_issue_block`
6. `test_book_return_on_time_and_overdue_fine` (₹5/day late fee calculation)
7. `test_delete_protection_with_active_loans`
