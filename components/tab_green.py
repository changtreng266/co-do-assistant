import pandas as pd
import streamlit as st
from config.settings import DIEM_DEN_DATA, get_checkin_codes
from services.auth_service import claim_green_credits, get_today_claim


def render_green_tab():
    st.header("Điều phối Du lịch Xanh Trục Di sản (Tam Chúc - Hoa Lư - Đền Trần)")
    user = st.session_state.user
    user_id = user["id"]

    data_diem_den = pd.DataFrame(DIEM_DEN_DATA)

    st.subheader("1. Bản đồ nhiệt mật độ khách trên toàn tuyến di sản")
    st.caption(
        "⚠️ **Dữ liệu mô phỏng** dùng để minh họa ý tưởng. Khi triển khai thực tế, số liệu sẽ được lấy "
        "từ hệ thống bán vé / cổng soát vé của các khu du lịch."
    )
    st.dataframe(data_diem_den, width="stretch", hide_index=True)

    st.markdown(
        '<div class="section-icon-heading"><i class="fa-solid fa-chart-column"></i>'
        '<span>Biểu đồ trực quan phân bổ lưu lượng khách (%) - mô phỏng</span></div>',
        unsafe_allow_html=True,
    )
    chart_data = data_diem_den.set_index("Địa điểm")["Mật độ khách (%)"]
    st.bar_chart(chart_data, color="#2d5a40")

    st.subheader("2. Tính toán Lộ trình Xanh & Nhận Tín chỉ")
    st.caption(
        "Để nhận Tín chỉ Xanh, bạn cần nhập **mã check-in** in trên bảng QR đặt tại điểm đến - "
        "chứng minh bạn đã thực sự có mặt tại đó."
    )

    checkin_codes, demo_codes = get_checkin_codes()
    if demo_codes:
        st.markdown(
            '<div class="section-icon-heading compact"><i class="fa-solid fa-flask"></i>'
            '<span>Chế độ trình diễn: xem mã check-in mẫu</span></div>',
            unsafe_allow_html=True,
        )
        with st.expander("Xem mã check-in mẫu"):
            st.dataframe(
                pd.DataFrame({"Điểm đến": list(checkin_codes.keys()), "Mã check-in": list(checkin_codes.values())}),
                width="stretch",
                hide_index=True,
            )

    today_claim = get_today_claim(user_id)
    if today_claim:
        st.info(
            f"Hôm nay bạn đã xác nhận lộ trình đến **{today_claim['destination']}** "
            f"(tiết kiệm **{today_claim['co2_saved']} kg CO2**, nhận **+{today_claim['credits']} Tín chỉ Xanh**). "
            "Mỗi tài khoản được nhận thưởng lộ trình xanh 1 lần/ngày để đảm bảo công bằng."
        )

    col1, col2, col3 = st.columns(3)
    with col1:
        diem_chon = st.selectbox("Chọn điểm đến:", data_diem_den["Địa điểm"], key="green_dest")
    with col2:
        phuong_tien = st.selectbox(
            "Phương tiện di chuyển:",
            ("Xe đạp", "Đi bộ / Thuyền nan", "Xe điện / Xe buýt liên vùng", "Ô tô cá nhân / Xe máy"),
            key="green_vehicle",
        )
    with col3:
        khoang_cach = st.number_input(
            "Quãng đường dự kiến (km):", min_value=1, max_value=50, value=10, key="green_dist"
        )

    ma_checkin = st.text_input(
        "Mã check-in tại điểm đến:",
        key="green_checkin_code",
        placeholder="Nhập mã in trên bảng QR tại điểm đến",
    )

    flash = st.session_state.pop("green_flash", None)
    if flash:
        st.success(flash[0])
        st.info(flash[1])

    if st.button("Phân tích & Xác nhận lộ trình", type="primary", key="btn_claim_green"):
        co2_tiet_kiem = 0.0
        diem_cong = 0

        if phuong_tien in ("Xe đạp", "Đi bộ / Thuyền nan"):
            co2_tiet_kiem = round(khoang_cach * 0.15, 2)
            diem_cong += int(khoang_cach * 2)
        elif phuong_tien == "Xe điện / Xe buýt liên vùng":
            co2_tiet_kiem = round(khoang_cach * 0.08, 2)
            diem_cong += int(khoang_cach * 1)

        if diem_cong <= 0:
            st.warning(
                "Phương tiện cá nhân chạy xăng/dầu không phát sinh Tín chỉ Xanh. "
                "Hãy chọn xe đạp, đi bộ/thuyền nan hoặc xe buýt điện để nhận điểm thưởng nhé!"
            )
            return

        ma_dung = checkin_codes.get(diem_chon, "")
        if not ma_dung or ma_checkin.strip().upper() != ma_dung.strip().upper():
            st.error(
                f"Mã check-in không đúng với **{diem_chon}**. Hãy quét/nhập mã trên bảng QR đặt tại điểm đến."
            )
            return

        dong_chon = data_diem_den.loc[data_diem_den["Địa điểm"] == diem_chon]
        trang_thai_diem = str(dong_chon["Trạng thái"].values[0])

        if "🟢" in trang_thai_diem:
            diem_cong += 15
            loi_khuyen = (
                f"Tuyệt vời! **{diem_chon}** đang rất thoáng. Bạn được thưởng thêm **15 điểm** "
                "vì góp phần giãn cách mật độ khách trên trục di sản."
            )
        else:
            loi_khuyen = (
                f"Lưu ý: **{diem_chon}** đang khá đông. Hãy cân nhắc ghé **Đầm Vân Long** hoặc "
                "**Vườn Quốc gia Xuân Thủy** để có trải nghiệm xanh trọn vẹn hơn."
            )

        claimed, actual_points = claim_green_credits(user_id, diem_chon, diem_cong, co2_tiet_kiem)
        if claimed:
            # Lưu thông báo rồi chạy lại trang để số dư ở thanh bên cập nhật ngay,
            # thông báo sẽ hiện lại sau khi chạy lại (không bị mất như khi gọi st.rerun() trực tiếp)
            st.session_state.green_flash = (
                f"Kết quả: Bạn giảm được **{co2_tiet_kiem} kg CO2** và nhận được **+{actual_points} Tín chỉ Xanh**!",
                loi_khuyen,
            )
            st.rerun()
        else:
            st.warning(
                "Hôm nay bạn đã nhận điểm thưởng lộ trình xanh rồi. Hãy quay lại vào ngày mai để tiếp tục tích điểm nhé!"
            )
