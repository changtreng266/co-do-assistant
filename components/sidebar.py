import html
import streamlit as st
from config.settings import MAX_DAILY_CHATS
from services.auth_service import (
    authenticate_user,
    get_daily_chat_used,
    get_green_credits,
    register_user,
)


def render_sidebar() -> bool:
    """Hiển thị thanh bên với giao diện Glassmorphism & Font Awesome."""
    with st.sidebar:
        st.markdown(
            """
            <div class="codo-brand-card">
                <div class="codo-brand-title">
                    <i class="fa-solid fa-landmark"></i>
                    <span>Cố Đô AI</span>
                </div>
                <div class="codo-brand-sub">
                    <i class="fa-solid fa-location-dot"></i> Trợ lý Du lịch Thông minh Liên vùng<br>
                    Hà Nam • Nam Định • Ninh Bình
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        user = st.session_state.get("user")
        if not user:
            tab_login, tab_reg = st.tabs(["Đăng nhập", "Đăng ký"])

            with tab_login:
                with st.form("sidebar_login_form"):
                    username = st.text_input(
                        "Tên đăng nhập", placeholder="Nhập tên tài khoản..."
                    )
                    password = st.text_input(
                        "Mật khẩu", type="password", placeholder="••••••••"
                    )
                    submitted = st.form_submit_button(
                        "Đăng nhập", type="primary", width="stretch"
                    )
                    if submitted:
                        auth_user = authenticate_user(username, password)
                        if auth_user:
                            st.session_state.user = auth_user
                            st.rerun()
                        else:
                            st.error("Sai tên đăng nhập hoặc mật khẩu!")

            with tab_reg:
                with st.form("sidebar_register_form"):
                    new_user = st.text_input("Tên đăng nhập (viết liền)")
                    new_pass = st.text_input("Mật khẩu (8–128 ký tự)", type="password")
                    confirm_pass = st.text_input("Nhập lại mật khẩu", type="password")
                    reg_submitted = st.form_submit_button(
                        "Tạo tài khoản (+50 điểm)", width="stretch"
                    )
                    if reg_submitted:
                        if new_pass != confirm_pass:
                            st.error("Mật khẩu nhập lại chưa khớp!")
                        else:
                            ok, msg = register_user(new_user, new_pass)
                            if ok:
                                st.success(msg)
                            else:
                                st.error(msg)

            st.markdown(
                """
                <div style="font-size:0.84rem; color:#475569; background:rgba(16,185,129,0.08);
                            padding:12px; border-radius:12px; border:1px solid rgba(16,185,129,0.2);">
                    <i class="fa-solid fa-circle-info" style="color:#059669;"></i>
                    Tạo tài khoản để lưu lịch trình AI, tích lũy <b>Tín chỉ Xanh</b> và đổi quà làng nghề.
                </div>
                """,
                unsafe_allow_html=True,
            )
            return False

        current_credits = get_green_credits(user["id"])
        st.session_state.user["green_credits"] = current_credits

        used_chats = get_daily_chat_used(user["id"])
        remaining_chats = max(0, MAX_DAILY_CHATS - used_chats)

        safe_username = html.escape(str(user.get("username", "")), quote=True)
        st.markdown(
            f"""
            <div style="display:flex; align-items:center; gap:8px; padding:10px 12px;
                        background:rgba(16,185,129,0.12); border-radius:12px; margin-bottom:12px;
                        color:#065f46; font-weight:600;">
                <i class="fa-solid fa-user-check"></i>
                <span>Xin chào, {safe_username}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.metric(label="Tín chỉ Xanh của bạn", value=f"{current_credits} điểm")

        st.progress(
            remaining_chats / MAX_DAILY_CHATS,
            text=f"Lượt hỏi AI hôm nay: {remaining_chats}/{MAX_DAILY_CHATS}",
        )

        st.markdown(
            """
            <div style="font-size:0.8rem; color:#475569; margin-top:8px;">
                <i class="fa-solid fa-leaf" style="color:#10b981;"></i>
                Tích điểm tại Tab <b>Du lịch Xanh</b> và đổi quà tại Gốm Bồ Bát, Lụa Nha Xá, Đúc đồng Tống Xá.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()
        if st.button("Đăng xuất", width="stretch"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

        return True