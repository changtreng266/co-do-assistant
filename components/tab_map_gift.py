import hmac
import pandas as pd
import streamlit as st
from config.settings import BAN_DO_DATA, DANH_SACH_QUA, get_staff_pin
from services.auth_service import (
    get_green_credits,
    get_user_redemptions,
    redeem_gift,
    verify_and_use_voucher,
)


def render_map_gift_tab():
    st.header("Bản đồ Số Trục Di sản & Đổi quà Tín chỉ Xanh")
    user = st.session_state.user
    user_id = user["id"]

    col_map, col_gift = st.columns(2)

    with col_map:
        st.markdown(
            '<div class="section-icon-heading"><i class="fa-solid fa-location-dot"></i>'
            '<span>Tọa độ Các Điểm Di sản & Làng nghề</span></div>',
            unsafe_allow_html=True,
        )
        st.caption("Bản đồ phân bố các điểm du lịch xanh và làng nghề truyền thống liên vùng.")
        du_lieu_ban_do = pd.DataFrame(BAN_DO_DATA)
        st.map(du_lieu_ban_do, zoom=9)
        st.dataframe(du_lieu_ban_do[["Địa điểm"]], width="stretch", hide_index=True)

    with col_gift:
        st.markdown(
            '<div class="section-icon-heading"><i class="fa-solid fa-gift"></i>'
            '<span>Đổi Tín chỉ Xanh lấy Quà Làng nghề</span></div>',
            unsafe_allow_html=True,
        )
        current_credits = get_green_credits(user_id)
        st.info(f"Số dư hiện tại của bạn: **{current_credits} Tín chỉ Xanh**")

        flash = st.session_state.pop("gift_flash", None)
        if flash:
            gift_name, code = flash
            st.success(f"Chúc mừng! Bạn đã đổi thành công **{gift_name}**.")
            st.code(f"MÃ ƯU ĐÃI CỦA BẠN: {code}", language="text")
            st.caption("Xuất trình mã này tại quầy lưu niệm làng nghề hoặc cổng soát vé để nhận quà.")

        qua_chon = st.selectbox(
            "Chọn phần quà hoặc ưu đãi:",
            tuple(DANH_SACH_QUA.keys()),
            key="gift_select",
        )
        diem_can = DANH_SACH_QUA[qua_chon]
        st.write(f"Chi phí đổi quà: **{diem_can} điểm**")

        if st.button("Xác nhận đổi quà ngay", type="primary", key="btn_redeem_gift"):
            if current_credits >= diem_can:
                ok, result = redeem_gift(user_id, qua_chon, diem_can)
                if ok:
                    # Lưu thông báo rồi chạy lại để số dư cập nhật, mã voucher vẫn hiển thị sau khi chạy lại
                    st.session_state.gift_flash = (qua_chon, result)
                    st.rerun()
                else:
                    st.error(result)
            else:
                diem_thieu = diem_can - current_credits
                st.warning(
                    f"Bạn còn thiếu **{diem_thieu} điểm** nữa. Hãy sang Tab **Du lịch Xanh** để tích thêm điểm nhé!"
                )

        # Hiển thị lịch sử các voucher đã đổi của người dùng
        redemptions = get_user_redemptions(user_id)
        if redemptions:
            st.divider()
            st.markdown(
                '<div class="section-icon-heading compact"><i class="fa-solid fa-ticket"></i>'
                '<span>Ví Voucher của bạn</span></div>',
                unsafe_allow_html=True,
            )
            df_vouchers = pd.DataFrame(redemptions)
            st.dataframe(df_vouchers, width="stretch", hide_index=True)

    st.divider()
    _render_staff_verification()


def _render_staff_verification():
    """Khu vực dành cho nhân viên làng nghề kiểm tra và xác nhận voucher của du khách."""
    st.markdown(
        '<div class="section-icon-heading compact"><i class="fa-solid fa-store"></i>'
        '<span>Dành cho làng nghề / quầy quà tặng</span></div>',
        unsafe_allow_html=True,
    )
    with st.expander("Xác nhận voucher"):
        staff_pin = get_staff_pin()
        if not staff_pin:
            st.caption(
                "Chức năng chưa bật. Quản trị viên cần khai báo `STAFF_PIN` trong `.streamlit/secrets.toml`."
            )
            return

        with st.form("staff_verify_form", clear_on_submit=True):
            code = st.text_input("Mã voucher của khách (VD: CODOAI-1A2B3C4D5E6F7788)")
            pin = st.text_input("Mã PIN nhân viên", type="password")
            submitted = st.form_submit_button("Kiểm tra & xác nhận đã trao quà")

        if submitted:
            if not hmac.compare_digest(pin, staff_pin):
                st.error("Mã PIN nhân viên không đúng.")
                return
            ok, msg = verify_and_use_voucher(code)
            if ok:
                st.success(msg)
            else:
                st.error(msg)
