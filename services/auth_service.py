import hashlib
import hmac
import math
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from config.settings import DANH_SACH_QUA, DIEM_DEN_DATA, MAX_DAILY_CHATS

DATABASE_PATH = Path(__file__).resolve().parent.parent / "co-do-ai.sqlite3"

# Giờ Việt Nam (UTC+7). Server Streamlit Cloud chạy giờ UTC, nếu dùng date.today()
# thì "ngày mới" sẽ bắt đầu lúc 7h sáng giờ Việt Nam.
VN_TZ = timezone(timedelta(hours=7))


def _today() -> str:
    return datetime.now(VN_TZ).date().isoformat()


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database() -> None:
    with _get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                password_iterations INTEGER NOT NULL DEFAULT 100000,
                green_credits INTEGER NOT NULL DEFAULT 50 CHECK(green_credits >= 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                conversation TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_chat_messages_user_conversation
                ON chat_messages(user_id, conversation, id);

            CREATE TABLE IF NOT EXISTS chat_usage (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                usage_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_chat_usage_user_date
                ON chat_usage(user_id, usage_date);

            CREATE TABLE IF NOT EXISTS green_claims (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                claim_date TEXT NOT NULL,
                destination TEXT NOT NULL,
                credits INTEGER NOT NULL,
                co2_saved REAL NOT NULL,
                UNIQUE(user_id, claim_date)
            );

            CREATE TABLE IF NOT EXISTS redemptions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                gift TEXT NOT NULL,
                credits INTEGER NOT NULL,
                voucher_code TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                used_at TEXT
            );
            """
        )
        # Nâng cấp CSDL cũ theo hướng tương thích ngược.
        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "password_iterations" not in user_columns:
            # Hash cũ được tạo với 100.000 vòng PBKDF2; giữ đúng số vòng để tài khoản cũ đăng nhập được.
            conn.execute("ALTER TABLE users ADD COLUMN password_iterations INTEGER NOT NULL DEFAULT 100000")

        redemption_columns = {row["name"] for row in conn.execute("PRAGMA table_info(redemptions)")}
        if "used_at" not in redemption_columns:
            conn.execute("ALTER TABLE redemptions ADD COLUMN used_at TEXT")


PASSWORD_ITERATIONS = 310_000


def _hash_password(password: str, salt: str, iterations: int = PASSWORD_ITERATIONS) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return dk.hex()


def register_user(username: str, password: str) -> tuple[bool, str]:
    clean_user = username.strip()
    if not re.fullmatch(r"[\w.-]{3,32}", clean_user, flags=re.UNICODE):
        return False, "Tên đăng nhập phải dài 3–32 ký tự, chỉ gồm chữ, số, dấu gạch dưới, chấm hoặc gạch ngang."
    if not 8 <= len(password) <= 128:
        return False, "Mật khẩu phải có độ dài từ 8 đến 128 ký tự."

    salt = secrets.token_hex(16)
    pwd_hash = _hash_password(password, salt, PASSWORD_ITERATIONS)

    try:
        with _get_connection() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, password_salt, password_iterations, green_credits) VALUES (?, ?, ?, ?, 50)",
                (clean_user, pwd_hash, salt, PASSWORD_ITERATIONS),
            )
        return True, "Đăng ký thành công! Bạn được tặng 50 Tín chỉ Xanh khởi đầu."
    except sqlite3.IntegrityError:
        return False, "Tên đăng nhập này đã tồn tại."


def authenticate_user(username: str, password: str) -> dict | None:
    clean_user = username.strip()
    if not clean_user or not password or len(password) > 128:
        return None

    with _get_connection() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, password_salt, password_iterations, green_credits FROM users WHERE username = ?",
            (clean_user,),
        ).fetchone()

    if not row:
        return None

    iterations = int(row["password_iterations"])
    expected_hash = _hash_password(password, row["password_salt"], iterations)
    if not hmac.compare_digest(expected_hash, row["password_hash"]):
        return None

    # Tự nâng cấp hash cũ sau lần đăng nhập thành công, không buộc người dùng đổi mật khẩu.
    if iterations < PASSWORD_ITERATIONS:
        new_salt = secrets.token_hex(16)
        new_hash = _hash_password(password, new_salt, PASSWORD_ITERATIONS)
        with _get_connection() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, password_salt = ?, password_iterations = ? WHERE id = ?",
                (new_hash, new_salt, PASSWORD_ITERATIONS, row["id"]),
            )

    return {
        "id": row["id"],
        "username": row["username"],
        "green_credits": row["green_credits"],
    }


def get_green_credits(user_id: int) -> int:
    with _get_connection() as conn:
        row = conn.execute("SELECT green_credits FROM users WHERE id = ?", (user_id,)).fetchone()
    return int(row["green_credits"]) if row else 0


def load_messages(user_id: int, conversation: str) -> list[dict]:
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT role, content FROM chat_messages WHERE user_id = ? AND conversation = ? ORDER BY id ASC",
            (user_id, conversation),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def save_message(user_id: int, conversation: str, role: str, content: str) -> None:
    if role not in ("user", "assistant") or not content.strip():
        raise ValueError("Tin nhắn không hợp lệ.")
    with _get_connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, conversation, role, content) VALUES (?, ?, ?, ?)",
            (user_id, conversation, role, content.strip()),
        )


def save_chat_turn(user_id: int, conversation: str, user_content: str, assistant_content: str) -> None:
    """Lưu cả lượt hỏi và đáp trong một transaction để không tạo lịch sử bị cụt."""
    user_text = user_content.strip()
    assistant_text = assistant_content.strip()
    if not user_text or not assistant_text:
        raise ValueError("Nội dung lượt trò chuyện không được để trống.")
    with _get_connection() as conn:
        conn.executemany(
            "INSERT INTO chat_messages (user_id, conversation, role, content) VALUES (?, ?, ?, ?)",
            [
                (user_id, conversation, "user", user_text),
                (user_id, conversation, "assistant", assistant_text),
            ],
        )


def clear_messages(user_id: int, conversation: str) -> None:
    with _get_connection() as conn:
        conn.execute(
            "DELETE FROM chat_messages WHERE user_id = ? AND conversation = ?",
            (user_id, conversation),
        )


def get_daily_chat_used(user_id: int) -> int:
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM chat_usage WHERE user_id = ? AND usage_date = ?",
            (user_id, _today()),
        ).fetchone()
    return int(row["cnt"]) if row else 0


def consume_chat_quota(user_id: int) -> tuple[bool, int | None]:
    """Trừ 1 lượt hỏi AI. Trả về (thành công, id lượt dùng để hoàn lại nếu AI lỗi)."""
    today_str = _today()
    with _get_connection() as conn:
        # Kiểm tra và ghi trong cùng một câu lệnh để không vượt giới hạn khi bấm gửi liên tục
        cur = conn.execute(
            """
            INSERT INTO chat_usage (user_id, usage_date)
            SELECT ?, ?
            WHERE (SELECT COUNT(*) FROM chat_usage WHERE user_id = ? AND usage_date = ?) < ?
            """,
            (user_id, today_str, user_id, today_str, MAX_DAILY_CHATS),
        )
        if cur.rowcount == 0:
            return False, None
        return True, cur.lastrowid


def refund_chat_quota(usage_id: int | None) -> None:
    """Hoàn lại lượt hỏi khi AI không trả lời được (lỗi mạng, quá tải...)."""
    if usage_id is None:
        return
    with _get_connection() as conn:
        conn.execute("DELETE FROM chat_usage WHERE id = ?", (usage_id,))


def get_today_claim(user_id: int) -> dict | None:
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT destination, credits, co2_saved FROM green_claims WHERE user_id = ? AND claim_date = ?",
            (user_id, _today()),
        ).fetchone()
    return dict(row) if row else None


def claim_green_credits(user_id: int, destination: str, credits: int, co2_saved: float) -> tuple[bool, int]:
    allowed_destinations = set(DIEM_DEN_DATA["Địa điểm"])
    if destination not in allowed_destinations:
        return False, 0
    if not isinstance(credits, int) or not 1 <= credits <= 200:
        return False, 0
    if not isinstance(co2_saved, (int, float)) or not math.isfinite(float(co2_saved)) or not 0 <= co2_saved <= 1000:
        return False, 0

    try:
        with _get_connection() as conn:
            conn.execute(
                "INSERT INTO green_claims (user_id, claim_date, destination, credits, co2_saved) VALUES (?, ?, ?, ?, ?)",
                (user_id, _today(), destination, credits, co2_saved),
            )
            conn.execute(
                "UPDATE users SET green_credits = green_credits + ? WHERE id = ?",
                (credits, user_id),
            )
        return True, credits
    except sqlite3.IntegrityError:
        return False, 0


def redeem_gift(user_id: int, gift: str, cost: int) -> tuple[bool, str]:
    expected_cost = DANH_SACH_QUA.get(gift)
    if expected_cost is None or not isinstance(cost, int) or cost != expected_cost or cost <= 0:
        return False, "Phần quà hoặc số điểm đổi không hợp lệ."
    voucher_code = f"CODOAI-{secrets.token_hex(8).upper()}"
    with _get_connection() as conn:
        # Chỉ trừ điểm khi còn đủ số dư - kiểm tra và trừ trong cùng một câu lệnh,
        # tránh bị trừ âm khi bấm "Đổi quà" nhiều lần liên tiếp.
        cur = conn.execute(
            "UPDATE users SET green_credits = green_credits - ? WHERE id = ? AND green_credits >= ?",
            (cost, user_id, cost),
        )
        if cur.rowcount == 0:
            return False, "Số dư Tín chỉ Xanh không đủ để đổi phần quà này."

        conn.execute(
            "INSERT INTO redemptions (user_id, gift, credits, voucher_code) VALUES (?, ?, ?, ?)",
            (user_id, gift, cost, voucher_code),
        )
    return True, voucher_code


def get_user_redemptions(user_id: int) -> list[dict]:
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT gift AS "Quà đã đổi",
                   credits AS "Điểm",
                   voucher_code AS "Mã Voucher",
                   CASE WHEN used_at IS NULL THEN 'Chưa sử dụng' ELSE 'Đã sử dụng' END AS "Trạng thái",
                   created_at AS "Thời gian"
            FROM redemptions
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def verify_and_use_voucher(voucher_code: str) -> tuple[bool, str]:
    """Dành cho nhân viên làng nghề: kiểm tra mã voucher và đánh dấu đã sử dụng."""
    code = voucher_code.strip().upper()
    if not re.fullmatch(r"CODOAI-(?:[A-F0-9]{8}|[A-F0-9]{16})", code):
        return False, "Mã voucher không đúng định dạng."

    with _get_connection() as conn:
        row = conn.execute(
            """
            SELECT r.gift, r.used_at, u.username
            FROM redemptions r JOIN users u ON u.id = r.user_id
            WHERE r.voucher_code = ?
            """,
            (code,),
        ).fetchone()
        if not row:
            return False, f"Không tìm thấy mã **{code}**. Mã có thể bị nhập sai hoặc là mã giả."
        if row["used_at"]:
            return False, f"Mã **{code}** đã được sử dụng lúc {row['used_at']} (UTC)."

        cur = conn.execute(
            "UPDATE redemptions SET used_at = CURRENT_TIMESTAMP WHERE voucher_code = ? AND used_at IS NULL",
            (code,),
        )
        if cur.rowcount == 0:
            return False, f"Mã **{code}** vừa được sử dụng."

    return True, f"Hợp lệ! Trao **{row['gift']}** cho khách **{row['username']}**. Mã đã được đánh dấu đã sử dụng."
