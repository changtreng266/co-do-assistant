from pathlib import Path
import streamlit as st

from components.sidebar import render_sidebar
from components.tab_green import render_green_tab
from components.tab_guide import render_guide_tab
from components.tab_history import render_history_tab
from components.tab_map_gift import render_map_gift_tab
from services.auth_service import initialize_database

st.set_page_config(
    page_title="Cố Đô AI - Trợ Lý Du Lịch Thông Minh",
    page_icon="🏛️",
    layout="wide",
)

initialize_database()

stylesheet_path = Path(__file__).resolve().parent / "assets" / "style.css"
if stylesheet_path.exists():
    with stylesheet_path.open(encoding="utf-8") as stylesheet:
        st.markdown(f"<style>{stylesheet.read()}</style>", unsafe_allow_html=True)

is_logged_in = render_sidebar()
if not is_logged_in:
    st.markdown(
        """
        <div class="welcome-hero">
            <div class="welcome-pill">
                <i class="fa-solid fa-sparkles"></i>
                <span>Hệ sinh thái Du lịch Thông minh & Bền vững</span>
            </div>
            <h2>Khám phá Trục Di sản Hà Nam • Nam Định • Ninh Bình</h2>
            <p>
                Trải nghiệm hành trình kết nối <b>Tam Chúc - Hoa Lư - Đền Trần</b> cùng trợ lý AI đa phương thức,
                trò chuyện trực tiếp với các bậc danh nhân lịch sử và tích lũy <b>Tín chỉ Xanh</b> đổi quà làng nghề truyền thống.
            </p>
            <div class="welcome-cta-hint">
                <i class="fa-solid fa-arrow-left"></i>
                <span>Đăng nhập hoặc tạo tài khoản ở thanh bên trái (+50 điểm khởi đầu)</span>
            </div>
        </div>

        <div class="feature-grid">
            <div class="feature-card">
                <div class="feature-icon"><i class="fa-solid fa-compass"></i></div>
                <h4>Hướng dẫn viên AI Thông minh</h4>
                <p>Thiết kế lịch trình 1-3 ngày, gợi ý ẩm thực đặc sản, giá vé tham quan và hỗ trợ hỏi đáp trực tiếp bằng giọng nói.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon"><i class="fa-solid fa-crown"></i></div>
                <h4>Đối thoại cùng Danh nhân</h4>
                <p>Đàm đạo cùng Vua Đinh Tiên Hoàng, Hưng Đạo Đại Vương, Thái hậu Dương Vân Nga và Thiền sư Nguyễn Minh Không kèm giọng đọc AI.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon"><i class="fa-solid fa-leaf"></i></div>
                <h4>Điều phối Du lịch Xanh</h4>
                <p>Theo dõi mật độ khách liên vùng, chọn phương tiện ít phát thải CO₂ và quét mã check-in nhận thưởng Tín chỉ Xanh mỗi ngày.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon"><i class="fa-solid fa-gift"></i></div>
                <h4>Bản đồ Số & Quà Làng nghề</h4>
                <p>Định vị các điểm di sản và đổi điểm lấy voucher lụa Nha Xá, gốm Bồ Bát, đúc đồng Tống Xá với mã xác nhận tại quầy.</p>
            </div>
        </div>

        <div class="stats-strip">
            <div class="stat-item">
                <strong>3 Tỉnh</strong>
                <span>Trục Di sản Liên vùng</span>
            </div>
            <div class="stat-item">
                <strong>4 Danh nhân</strong>
                <span>Đối thoại Lịch sử AI</span>
            </div>
            <div class="stat-item">
                <strong>+50 Điểm</strong>
                <span>Tặng ngay khi đăng ký</span>
            </div>
            <div class="stat-item">
                <strong>24/7</strong>
                <span>Hỗ trợ Giọng nói & Text</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

st.title("🏛️ Cố Đô AI - Hành Trình Di Sản Xanh")
st.caption("Kết nối Tam Chúc • Cố đô Hoa Lư • Phủ Thiên Trường")

st.markdown(
    """
    <div class="codo-hero">
        <div>
            <h1><i class="fa-solid fa-compass"></i> Hệ sinh thái Du lịch Thông minh Cố Đô AI</h1>
            <div style="color:#475569; font-size:0.9rem; margin-top:4px;">
                Kết nối di sản Tam Chúc • Hoa Lư • Đền Trần cùng trải nghiệm Du lịch Xanh bền vững
            </div>
        </div>
        <div class="codo-badge">
            <i class="fa-solid fa-sparkles"></i> AI Powered • Green Tourism
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

tabs = st.tabs(
    (
        "Hướng dẫn viên AI",
        "Du lịch Xanh",
        "Đối thoại Danh nhân",
        "Bản đồ & Đổi quà",
    )
)

with tabs[0]:
    render_guide_tab()
with tabs[1]:
    render_green_tab()
with tabs[2]:
    render_history_tab()
with tabs[3]:
    render_map_gift_tab()