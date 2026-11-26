import streamlit as st
from config.settings import DANH_MUC_OPTIONS, KHU_VUC_OPTIONS, MAX_DAILY_CHATS
from services.auth_service import (
    clear_messages,
    consume_chat_quota,
    load_messages,
    refund_chat_quota,
    save_chat_turn,
)
from services.gemini_service import VOICE_PREFIX, fetch_gemini_reply, stream_text_smoothly

CONVERSATION = "guide"


def render_guide_tab():
    st.header("Hướng dẫn viên AI Khám phá Vùng Di sản")
    st.caption("Tư vấn lịch trình Tam Chúc - Hoa Lư - Đền Trần, ẩm thực đặc sản, giá vé và làng nghề truyền thống.")

    user = st.session_state.user
    user_id = user["id"]

    if "mic_guide_idx" not in st.session_state:
        st.session_state.mic_guide_idx = 0

    col_kv, col_dm, col_clear = st.columns([2, 2, 1])
    with col_kv:
        khu_vuc = st.selectbox("Điểm đến quan tâm:", KHU_VUC_OPTIONS, key="guide_khu_vuc")
    with col_dm:
        danh_muc = st.selectbox("Chủ đề khám phá:", DANH_MUC_OPTIONS, key="guide_danh_muc")
    with col_clear:
        st.write("")
        st.write("")
        icon_col, button_col = st.columns([0.22, 1])
        with icon_col:
            st.markdown('<div class="control-icon"><i class="fa-solid fa-rotate-right"></i></div>', unsafe_allow_html=True)
        with button_col:
            if st.button("Làm mới chat", key="clear_guide_btn", width="stretch"):
                clear_messages(user_id, CONVERSATION)
                st.session_state.mic_guide_idx += 1
                st.rerun()

    st.markdown("**Gợi ý khám phá nhanh (Bấm để hỏi ngay):**")
    q_col1, q_col2, q_col3 = st.columns(3)
    quick_prompt = None
    with q_col1:
        icon_col, button_col = st.columns([0.16, 1])
        with icon_col:
            st.markdown('<div class="quick-action-icon"><i class="fa-regular fa-calendar-days"></i></div>', unsafe_allow_html=True)
        with button_col:
            if st.button("Lịch trình 1 ngày Tam Chúc - Tràng An?", width="stretch"):
                quick_prompt = (
                    "Hãy thiết kế giúp tôi một lịch trình du lịch hợp lý trong 1 ngày kết nối "
                    "Khu du lịch Tam Chúc (Hà Nam) và Quần thể danh thắng Tràng An (Ninh Bình)."
                )
    with q_col2:
        icon_col, button_col = st.columns([0.16, 1])
        with icon_col:
            st.markdown('<div class="quick-action-icon"><i class="fa-solid fa-utensils"></i></div>', unsafe_allow_html=True)
        with button_col:
            if st.button("Đặc sản nhất định phải thử ở 3 vùng?", width="stretch"):
                quick_prompt = (
                    "Giới thiệu những món ăn đặc sản nổi tiếng nhất mà du khách nhất định phải thưởng thức "
                    "khi đi qua trục Hà Nam - Nam Định - Ninh Bình."
                )
    with q_col3:
        icon_col, button_col = st.columns([0.16, 1])
        with icon_col:
            st.markdown('<div class="quick-action-icon"><i class="fa-solid fa-gift"></i></div>', unsafe_allow_html=True)
        with button_col:
            if st.button("Mua quà gì tại các làng nghề?", width="stretch"):
                quick_prompt = (
                    "Gợi ý cho du khách các sản phẩm thủ công mỹ nghệ đặc sắc tại các làng nghề truyền thống "
                    "vùng Hà Nam, Nam Định, Ninh Bình để mua về làm quà."
                )

    # Tải lịch sử chat riêng của tài khoản hiện tại từ SQLite
    messages = load_messages(user_id, CONVERSATION)
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Key động cho mic giúp tự động xóa bản ghi âm sau khi đã gửi
    st.markdown(
        '<div class="audio-input-label"><i class="fa-solid fa-microphone"></i>'
        '<span>Bấm Micro để hỏi bằng giọng nói:</span></div>',
        unsafe_allow_html=True,
    )
    audio_tourist = st.audio_input(
        " ",
        key=f"mic_guide_{st.session_state.mic_guide_idx}",
        label_visibility="collapsed",
    )
    user_input = st.chat_input(
        "Hỏi về lịch trình (VD: mở rộng thành 3 ngày), giá vé hoặc món ngon...",
        key="chat_input_guide",
    )
    final_prompt = quick_prompt or user_input

    if not (final_prompt or audio_tourist):
        return

    # Bản ghi âm đã được xử lý ở lượt này -> đổi key để lần chạy lại sau không gửi lại lần nữa
    audio_bytes = None
    if audio_tourist:
        if not final_prompt:
            audio_bytes = audio_tourist.getvalue()
        st.session_state.mic_guide_idx += 1

    allowed, usage_id = consume_chat_quota(user_id)
    if not allowed:
        st.warning(f"Bạn đã dùng hết {MAX_DAILY_CHATS} lượt hỏi AI hôm nay. Vui lòng quay lại vào ngày mai!")
        return

    if final_prompt:
        display_user_msg = final_prompt
        api_messages = messages + [{"role": "user", "content": final_prompt}]
    else:
        display_user_msg = f"{VOICE_PREFIX} *Đang nghe câu hỏi của bạn...*"
        api_messages = messages

    with st.chat_message("user"):
        st.markdown(display_user_msg)

    system_instruction = (
        "Bạn là Hướng dẫn viên Du lịch AI thông minh của vùng di sản liên tỉnh Hà Nam - Nam Định - Ninh Bình. "
        f"Khu vực du khách đang chọn: {khu_vuc}, chủ đề: {danh_muc}. "
        "QUAN TRỌNG: Hãy đọc kỹ toàn bộ lịch sử hội thoại trước đó. Nếu du khách vừa hỏi lịch trình 1 ngày và giờ yêu cầu mở rộng "
        "thành 2 hoặc 3 ngày ở khu vực tương tự, hãy kế thừa các điểm đã gợi ý và bổ sung lịch trình chi tiết từng buổi "
        "(Sáng - Trưa - Chiều - Tối) cho đủ số ngày yêu cầu. Trình bày rõ ràng bằng các gạch đầu dòng. "
        "Giá vé và giờ mở cửa có thể thay đổi, hãy nhắc du khách kiểm tra lại thông tin chính thức trước khi đi."
    )

    with st.chat_message("assistant"):
        with st.spinner("Hướng dẫn viên AI đang soạn câu trả lời..."):
            result = fetch_gemini_reply(
                messages=api_messages,
                system_instruction=system_instruction,
                temperature=0.5,
                audio_bytes=audio_bytes,
            )
        if not result.ok:
            # AI không trả lời được: hoàn lượt hỏi, không lưu thông báo lỗi vào lịch sử chat
            refund_chat_quota(usage_id)
            st.warning(result.text)
            return
        full_reply = st.write_stream(stream_text_smoothly(result.text))

    if final_prompt:
        saved_user_msg = final_prompt
    elif result.transcript:
        saved_user_msg = f"{VOICE_PREFIX} {result.transcript}"
    else:
        saved_user_msg = f"{VOICE_PREFIX} Du khách đã gửi câu hỏi bằng giọng nói; bản chép lời chưa khả dụng."

    save_chat_turn(user_id, CONVERSATION, saved_user_msg, str(full_reply))

    if audio_bytes:
        st.rerun()  # Hiển thị lại câu hỏi đã được chép thành chữ
