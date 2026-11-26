import streamlit as st

# Model và Base URL mặc định cho ShopAIKey Gateway (có thể đổi trong .streamlit/secrets.toml)
DEFAULT_MODEL_NAME = "gemini-3.8-flash"
DEFAULT_BASE_URL = "https://api.shopaikey.com/v1"
MAX_DAILY_CHATS = 30  # Giới hạn lượt hỏi AI/ngày/tài khoản chống spam token


def _get_secret(key: str, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        # Không có file secrets.toml
        return default


def get_api_key() -> str:
    return str(_get_secret("GEMINI_API_KEY", "") or "").strip()


def get_base_url() -> str:
    """Lấy Base URL cho Google GenAI SDK (không có /v1). Trả về chuỗi rỗng nếu dùng endpoint gốc Google."""
    url = str(_get_secret("GEMINI_BASE_URL", DEFAULT_BASE_URL) or DEFAULT_BASE_URL).strip()
    return url.rstrip("/")


def get_model_name() -> str:
    return str(_get_secret("GEMINI_MODEL", DEFAULT_MODEL_NAME) or DEFAULT_MODEL_NAME).strip() or DEFAULT_MODEL_NAME


def get_staff_pin() -> str:
    """Mã PIN nhân viên làng nghề dùng để xác nhận voucher. Trống = tắt chức năng."""
    return str(_get_secret("STAFF_PIN", "") or "")


KHU_VUC_OPTIONS = (
    "Toàn tuyến di sản (Hà Nam - Nam Định - Ninh Bình)",
    "Quần thể Tràng An - Cố đô Hoa Lư - Tam Cốc (Ninh Bình)",
    "Khu du lịch Tam Chúc - Địa Tạng Phi Lai Tự (Hà Nam)",
    "Đền Trần - Phủ Dày - Biển Thịnh Long (Nam Định)",
)

DANH_MUC_OPTIONS = (
    "Gợi ý lịch trình tham quan 1 - 3 ngày",
    "Ẩm thực đặc sản & Quán ngon địa phương",
    "Giá vé tham quan, giờ mở cửa & Lưu ý di chuyển",
    "Làng nghề truyền thống & Quà lưu niệm",
)

# LƯU Ý: Đây là DỮ LIỆU MÔ PHỎNG phục vụ trình diễn ý tưởng, chưa kết nối nguồn dữ liệu thời gian thực.
DIEM_DEN_DATA = {
    "Địa điểm": [
        "Tràng An - Bái Đính (Hoa Lư)",
        "Khu du lịch Tam Chúc (Kim Bảng)",
        "Đền Trần - Phủ Dày (Nam Định)",
        "Đầm Vân Long (Gia Viễn)",
        "Vườn Quốc gia Xuân Thủy (Giao Thủy)",
    ],
    "Mật độ khách (%)": [95, 80, 75, 30, 25],
    "Trạng thái": [
        "🔴 Quá tải",
        "🟠 Đông đúc",
        "🟠 Đông đúc",
        "🟢 Rất thoáng",
        "🟢 Rất thoáng",
    ],
    "Gợi ý điều phối liên vùng": [
        "Nên chuyển hướng sang Đầm Vân Long để trải nghiệm thuyền nan sinh thái.",
        "Nên tham quan vào buổi chiều hoặc kết hợp ghé làng lụa Nha Xá gần đó.",
        "Nên đi khung giờ sáng sớm hoặc chuyển hướng về vùng sinh thái ven biển.",
        "Khu bảo tồn ngập nước yên tĩnh, lý tưởng để đạp xe và ngắm voọc mông trắng.",
        "Rừng ngập mặn Ramsar ít phát thải, thích hợp du lịch sinh thái cộng đồng.",
    ],
}

# Mã check-in in trên bảng QR đặt tại từng điểm đến. Du khách phải nhập đúng mã
# mới được nhận Tín chỉ Xanh (chứng minh đã thực sự có mặt tại điểm đến).
# Khi triển khai thật, khai báo mã riêng trong secrets.toml (mục [CHECKIN_CODES])
# để mã không nằm công khai trong mã nguồn.
DEFAULT_CHECKIN_CODES = {
    "Tràng An - Bái Đính (Hoa Lư)": "TRANGAN",
    "Khu du lịch Tam Chúc (Kim Bảng)": "TAMCHUC",
    "Đền Trần - Phủ Dày (Nam Định)": "DENTRAN",
    "Đầm Vân Long (Gia Viễn)": "VANLONG",
    "Vườn Quốc gia Xuân Thủy (Giao Thủy)": "XUANTHUY",
}


def get_checkin_codes() -> tuple[dict[str, str], bool]:
    """Trả về (bảng mã check-in, đang_dùng_mã_demo)."""
    custom = _get_secret("CHECKIN_CODES")
    if custom:
        try:
            return {k: str(v) for k, v in dict(custom).items()}, False
        except Exception:
            pass
    return dict(DEFAULT_CHECKIN_CODES), True


BAN_DO_DATA = {
    "Địa điểm": [
        "Cố đô Hoa Lư - Tràng An (Ninh Bình)",
        "Khu du lịch Tam Chúc (Hà Nam)",
        "Đền Trần - Phủ Dày (Nam Định)",
        "Đầm Vân Long (Gia Viễn)",
        "Vườn Quốc gia Xuân Thủy (Giao Thủy)",
        "Làng Lụa Nha Xá (Duy Tiên)",
        "Làng Gốm Bồ Bát (Yên Mô)",
    ],
    "lat": [20.2586, 20.5736, 20.4539, 20.3889, 20.2333, 20.6653, 20.1456],
    "lon": [105.9136, 105.8058, 106.1628, 105.8858, 106.5333, 105.9814, 105.9681],
}

DANH_SACH_QUA = {
    "Voucher giảm 15% Khăn Lụa Nha Xá (Hà Nam)": 40,
    "Móc khóa Gốm Bồ Bát vẽ tay (Ninh Bình)": 60,
    "Vé trải nghiệm Đạp xe xuyên rừng Vân Long": 80,
    "Tượng đồng mini Làng nghề Tống Xá (Nam Định)": 100,
}

HISTORICAL_PROMPTS = {
    "Vua Đinh Tiên Hoàng (Đinh Bộ Lĩnh - Hoa Lư)": (
        "Bạn là Vua Đinh Tiên Hoàng (Đinh Bộ Lĩnh), người dẹp loạn 12 sứ quân, lập nên nước Đại Cồ Việt "
        "và định đô tại Hoa Lư năm 968. Hãy xưng 'Trẫm' và gọi du khách là 'Khanh' hoặc 'Quý khách phương xa'. "
        "Hãy ghi nhớ mạch trò chuyện trước đó với du khách. Giọng điệu uy nghi, hào sảng, hiếu khách."
    ),
    "Hưng Đạo Đại Vương Trần Quốc Tuấn (Phủ Thiên Trường - Nam Định)": (
        "Bạn là Quốc công Tiết chế Hưng Đạo Đại Vương Trần Quốc Tuấn, vị anh hùng dân tộc gắn liền với "
        "phủ Thiên Trường (Nam Định) và đền Trần Thương (Hà Nam). Hãy xưng 'Ta' và gọi du khách là 'Quý khách'. "
        "Hãy ghi nhớ mạch trò chuyện trước đó với du khách. Giọng điệu đĩnh đạc, anh minh, thấm nhuần hào khí Đông A."
    ),
    "Thái hậu Dương Vân Nga (Kinh đô Hoa Lư)": (
        "Bạn là Thái hậu Dương Vân Nga, người phụ nữ kiệt xuất gắn liền với hai triều đại Đinh - Tiền Lê "
        "tại kinh đô Hoa Lư. Hãy xưng 'Ta' và gọi du khách là 'Quý khách'. Hãy ghi nhớ mạch trò chuyện trước đó với du khách. "
        "Giọng điệu điềm đạm, sâu sắc, trí tuệ và giàu lòng yêu nước."
    ),
    "Thiền sư Nguyễn Minh Không (Bái Đính - Tam Chúc)": (
        "Bạn là Quốc sư Nguyễn Minh Không (Lý Quốc Sư) thời nhà Lý, người gắn liền với các ngôi cổ tự "
        "vùng núi đá vôi từ chùa Bái Đính (Ninh Bình) đến vùng Tam Chúc, Ba Sao (Hà Nam). "
        "Hãy xưng 'Bần tăng' và gọi du khách là 'Thí chủ'. Hãy ghi nhớ mạch trò chuyện trước đó với du khách. Giọng điệu từ bi, thanh tịnh."
    ),
}