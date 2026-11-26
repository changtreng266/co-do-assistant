"""Kiểm thử hồi quy cho tài khoản, SQLite, điểm xanh và voucher."""
import gc
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

import services.auth_service as auth
from config.settings import DANH_SACH_QUA, DIEM_DEN_DATA


class AuthServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db = auth.DATABASE_PATH
        auth.DATABASE_PATH = Path(self.temp_dir.name) / "test.sqlite3"
        auth.initialize_database()
        ok, message = auth.register_user("tester_01", "CorrectHorseBattery!")
        self.assertTrue(ok, message)
        self.user = auth.authenticate_user("TESTER_01", "CorrectHorseBattery!")

    def tearDown(self):
        auth.DATABASE_PATH = self.original_db
        gc.collect()
        self.temp_dir.cleanup()

    def test_registration_and_authentication(self):
        self.assertIsNotNone(self.user)
        self.assertIsNone(auth.authenticate_user("tester_01", "wrong-password"))
        self.assertFalse(auth.register_user("<script>", "CorrectHorseBattery!")[0])
        self.assertFalse(auth.register_user("short", "1234567")[0])

    def test_chat_turn_is_saved_as_a_pair(self):
        auth.save_chat_turn(self.user["id"], "guide", "Câu hỏi", "Câu trả lời")
        messages = auth.load_messages(self.user["id"], "guide")
        self.assertEqual([m["role"] for m in messages], ["user", "assistant"])
        self.assertEqual(messages[0]["content"], "Câu hỏi")

    def test_daily_quota_and_refund(self):
        usage_ids = []
        for _ in range(auth.MAX_DAILY_CHATS):
            ok, usage_id = auth.consume_chat_quota(self.user["id"])
            self.assertTrue(ok)
            usage_ids.append(usage_id)
        self.assertFalse(auth.consume_chat_quota(self.user["id"])[0])
        auth.refund_chat_quota(usage_ids[0])
        self.assertEqual(auth.get_daily_chat_used(self.user["id"]), auth.MAX_DAILY_CHATS - 1)

    def test_green_claim_validation_and_daily_uniqueness(self):
        destination = DIEM_DEN_DATA["Địa điểm"][0]
        self.assertEqual(auth.claim_green_credits(self.user["id"], destination, 20, 1.5), (True, 20))
        self.assertEqual(auth.claim_green_credits(self.user["id"], destination, 20, 1.5), (False, 0))
        self.assertEqual(auth.claim_green_credits(self.user["id"], destination, -5, 1.5), (False, 0))
        self.assertEqual(auth.claim_green_credits(self.user["id"], "Điểm không tồn tại", 20, 1.5), (False, 0))

    def test_gift_redemption_and_single_use_voucher(self):
        gift, cost = next(iter(DANH_SACH_QUA.items()))
        self.assertFalse(auth.redeem_gift(self.user["id"], gift, -cost)[0])
        ok, code = auth.redeem_gift(self.user["id"], gift, cost)
        self.assertTrue(ok)
        self.assertTrue(auth.verify_and_use_voucher(code)[0])
        self.assertFalse(auth.verify_and_use_voucher(code)[0])

    def test_legacy_database_migration_keeps_old_passwords_working(self):
        legacy_db = Path(self.temp_dir.name) / "legacy.sqlite3"
        salt = "legacy-salt"
        old_hash = hashlib.pbkdf2_hmac("sha256", b"OldPassword123", salt.encode(), 100_000).hex()
        with sqlite3.connect(legacy_db) as conn:
            conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT NOT NULL, password_salt TEXT NOT NULL, green_credits INTEGER NOT NULL DEFAULT 50, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            conn.execute("INSERT INTO users (username, password_hash, password_salt) VALUES (?, ?, ?)", ("legacy_user", old_hash, salt))
        auth.DATABASE_PATH = legacy_db
        auth.initialize_database()
        self.assertIsNotNone(auth.authenticate_user("legacy_user", "OldPassword123"))
        with sqlite3.connect(legacy_db) as conn:
            upgraded_iterations = conn.execute(
                "SELECT password_iterations FROM users WHERE username = ?", ("legacy_user",)
            ).fetchone()[0]
        self.assertEqual(upgraded_iterations, auth.PASSWORD_ITERATIONS)


if __name__ == "__main__":
    unittest.main()
