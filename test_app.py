"""
Unit & Integration Tests for Library Management System
Validates database creation, constraints, CRUD, issue limits, overdue fine calculations, and active loan delete protections.
"""

import os
import unittest
import tempfile
from datetime import date, timedelta
from main import DatabaseManager, FINE_PER_DAY, MAX_ACTIVE_LOANS, LOAN_PERIOD_DAYS


class TestLibraryManagementSystem(unittest.TestCase):
    def setUp(self):
        # Create a unique temporary database file for each test
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_file.close()
        self.db_path = self.temp_file.name
        self.db = DatabaseManager(db_path=self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except PermissionError:
                pass

    def test_schema_and_initial_seed(self):
        """Verifies database tables exist and sample data was correctly seeded."""
        stats = self.db.get_dashboard_stats()
        self.assertGreater(stats["total_titles"], 0)
        self.assertGreater(stats["total_members"], 0)
        self.assertGreater(stats["active_loans"], 0)

    def test_add_book_and_duplicate_isbn(self):
        """Tests adding a book and verifying available_copies = total_copies and duplicate ISBN blocking."""
        book_id = self.db.add_book(
            title="Design Patterns",
            author="Gang of Four",
            category="Computer Science",
            isbn="9780201633610",
            total_copies=5
        )
        self.assertIsNotNone(book_id)
        book = self.db.get_book(book_id)
        self.assertEqual(book["total_copies"], 5)
        self.assertEqual(book["available_copies"], 5)

        # Duplicate ISBN must raise ValueError
        with self.assertRaises(ValueError) as ctx:
            self.db.add_book("Duplicate Title", "Some Author", "Tech", "9780201633610", 2)
        self.assertIn("already exists", str(ctx.exception))

    def test_member_email_validation_and_duplicate(self):
        """Tests member email format validation and duplicate email check."""
        # Invalid email format
        with self.assertRaises(ValueError) as ctx:
            self.db.add_member("Bad Email User", "12345", "invalid-email-format", "Address")
        self.assertIn("Invalid email format", str(ctx.exception))

        # Valid registration
        mem_id = self.db.add_member("Valid User", "1234567890", "valid.user@test.com", "Main Road")
        self.assertIsNotNone(mem_id)

        # Duplicate email
        with self.assertRaises(ValueError) as ctx:
            self.db.add_member("Another User", "9876543210", "valid.user@test.com", "Other Road")
        self.assertIn("Duplicate email", str(ctx.exception))

    def test_borrow_limit_enforcement(self):
        """Tests that a member cannot borrow more than MAX_ACTIVE_LOANS (3)."""
        # Register a new member with 0 loans
        mem_id = self.db.add_member("Borrow Limit Tester", "9999999999", "borrower@test.com", "Street 1")

        # Add a book with 10 copies
        bk_id = self.db.add_book("Multi Copy Book", "Author X", "General", "9781112223334", 10)

        # Borrow 1st book
        self.db.issue_book(mem_id, bk_id)
        # Borrow 2nd book
        self.db.issue_book(mem_id, bk_id)
        # Borrow 3rd book
        self.db.issue_book(mem_id, bk_id)

        # Borrow 4th book must fail
        with self.assertRaises(ValueError) as ctx:
            self.db.issue_book(mem_id, bk_id)
        self.assertIn("Borrow limit reached", str(ctx.exception))

    def test_out_of_stock_issue_block(self):
        """Tests that a book with 0 available copies cannot be issued."""
        mem_id = self.db.add_member("Stock Tester", "8888888888", "stock@test.com", "Street 2")
        bk_id = self.db.add_book("Single Copy Book", "Author Y", "General", "9785556667778", 1)

        # First issue should succeed
        self.db.issue_book(mem_id, bk_id)

        # Verify available copies is now 0
        book = self.db.get_book(bk_id)
        self.assertEqual(book["available_copies"], 0)

        # Second issue attempt should raise "No copies available"
        mem2_id = self.db.add_member("Stock Tester 2", "7777777777", "stock2@test.com", "Street 3")
        with self.assertRaises(ValueError) as ctx:
            self.db.issue_book(mem2_id, bk_id)
        self.assertIn("No copies available", str(ctx.exception))

    def test_book_return_on_time_and_overdue_fine(self):
        """Tests return calculation: 0 fine for on-time return, ₹5/day for overdue."""
        mem_id = self.db.add_member("Return Tester", "6666666666", "return@test.com", "Street 4")
        bk_id = self.db.add_book("Returnable Book", "Author Z", "General", "9789998887771", 2)

        res = self.db.issue_book(mem_id, bk_id)
        tx_id = res["transaction_id"]

        # 1. On-time return
        ret_res = self.db.return_book(tx_id)
        self.assertEqual(ret_res["overdue_days"], 0)
        self.assertEqual(ret_res["fine"], 0.0)

        # Verify book copies restored
        book = self.db.get_book(bk_id)
        self.assertEqual(book["available_copies"], 2)

        # Attempting to return already returned transaction must fail
        with self.assertRaises(ValueError) as ctx:
            self.db.return_book(tx_id)
        self.assertIn("already been returned", str(ctx.exception))

        # 2. Simulate overdue loan by manually inserting an overdue transaction
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            past_issue = (date.today() - timedelta(days=20)).isoformat()
            past_due = (date.today() - timedelta(days=6)).isoformat()  # 6 days overdue
            cursor.execute("""
                INSERT INTO transactions (member_id, book_id, issue_date, due_date, status, fine)
                VALUES (?, ?, ?, ?, 'Issued', 0);
            """, (mem_id, bk_id, past_issue, past_due))
            cursor.execute("UPDATE books SET available_copies = available_copies - 1 WHERE book_id = ?;", (bk_id,))
            overdue_tx_id = cursor.lastrowid
            conn.commit()

        ret_overdue = self.db.return_book(overdue_tx_id)
        self.assertEqual(ret_overdue["overdue_days"], 6)
        expected_fine = 6 * FINE_PER_DAY
        self.assertEqual(ret_overdue["fine"], expected_fine)

    def test_delete_protection_with_active_loans(self):
        """Tests that books and members with active loans cannot be deleted."""
        mem_id = self.db.add_member("Protected Member", "5555555555", "prot@test.com", "Street 5")
        bk_id = self.db.add_book("Protected Book", "Author P", "General", "9784443332221", 2)

        self.db.issue_book(mem_id, bk_id)

        # Trying to delete book must fail
        with self.assertRaises(ValueError) as ctx:
            self.db.delete_book(bk_id)
        self.assertIn("active loan(s)", str(ctx.exception))

        # Trying to delete member must fail
        with self.assertRaises(ValueError) as ctx:
            self.db.delete_member(mem_id)
        self.assertIn("active unreturned loan(s)", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
