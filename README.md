# 🏛️ Cố Đô AI - Trợ lý Du lịch Thông minh

Hướng dẫn viên du lịch AI cho trục di sản Hà Nam - Nam Định - Ninh Bình.

## Chạy trên máy

```bash
pip install -r requirements.txt
copy .streamlit\secrets.toml.example .streamlit\secrets.toml   # rồi điền GEMINI_API_KEY
streamlit run app.py
```

## Kiểm thử logic

```bash
python -m unittest discover -s tests -v
```

## Cấu hình (`.streamlit/secrets.toml`)

| Khóa | Bắt buộc | Ý nghĩa |
|---|---|---|
| `GEMINI_API_KEY` | Có | API key lấy ở Google AI Studio |
| `GEMINI_MODEL` | Không | Tên model Gemini (mặc định ở `config/settings.py`) |
| `STAFF_PIN` | Không | PIN cho nhân viên làng nghề xác nhận voucher |
| `[CHECKIN_CODES]` | Không | Mã check-in riêng từng điểm đến; không khai báo thì dùng mã demo |

## Lưu ý khi deploy và nộp bài

- **Không nộp / đẩy lên GitHub file `secrets.toml` có key thật.** ZIP bàn giao chỉ chứa `secrets.toml.example`; hãy tự tạo `secrets.toml` trên máy triển khai.
- Nếu API key/PIN từng được chia sẻ trong ZIP, hãy thu hồi API key và thay PIN trước khi tiếp tục sử dụng.
- Tài khoản mới yêu cầu mật khẩu 8–128 ký tự; tài khoản cũ vẫn đăng nhập được nhờ cơ chế nâng cấp hash tương thích.
- **Dữ liệu lưu bằng SQLite (`co-do-ai.sqlite3`).** Trên Streamlit Community Cloud, ổ đĩa không cố định:
  mỗi lần app khởi động lại / deploy lại thì tài khoản, điểm và voucher sẽ bị xóa. Phù hợp để trình diễn;
  khi chạy thật cần chuyển sang cơ sở dữ liệu bên ngoài (VD: Supabase/PostgreSQL).
- **Số liệu mật độ khách là dữ liệu mô phỏng**, chưa kết nối nguồn thời gian thực.
- Ngày tính lượt hỏi AI / điểm thưởng theo giờ Việt Nam (UTC+7).

## Chống gian lận Tín chỉ Xanh

- Phải nhập **mã check-in** đặt tại điểm đến mới được nhận điểm (1 lần/ngày/tài khoản).
- Voucher có trạng thái **Chưa / Đã sử dụng**; nhân viên làng nghề xác nhận bằng mã PIN, mỗi mã chỉ dùng được 1 lần.
- Hạn chế còn lại: check-in bằng mã tĩnh vẫn có thể bị chia sẻ; một người vẫn có thể tạo nhiều tài khoản để nhận 50 điểm khởi đầu
  (hướng phát triển: xác thực số điện thoại / OTP).
