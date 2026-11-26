import streamlit as st
from config.settings import HISTORICAL_PROMPTS, MAX_DAILY_CHATS
from services.auth_service import (
    clear_messages,
    consume_chat_quota,
    load_messages,
    refund_chat_quota,
    save_chat_turn,
)
from services.gemini_service import (
    VOICE_PREFIX,
    fetch_gemini_reply,
    stream_text_smoothly,
    text_to_speech_vi,
)


def _conversation_key(nhan_vat: str) -> str:
    # Mỗi danh nhân có một cuộc trò chuyện riêng để AI không bị lẫn vai khi đổi nhân vật
    return f"history::{nhan_vat}"


def render_history_tab():
    st.header("Đối thoại cùng Danh nhân Đất Cố đô & Thiên Trường")
    st.caption("Trò chuyện trực tiếp cùng các bậc tiền nhân gắn liền với lịch sử Hoa Lư - Thiên Trường - Tam Chúc.")

    user = st.session_state.user
    user_id = user["id"]

    if "mic_history_idx" not in st.session_state:
        st.session_state.mic_history_idx = 0
    if "history_audio_cache" not in st.session_state:
        st.session_state.history_audio_cache = {}

    col_nv, col_voice, col_reset = st.columns([2.2, 1, 1])
    with col_nv:
        nhan_vat = st.selectbox(
            "Chọn danh nhân lịch sử:",
            tuple(HISTORICAL_PROMPTS.keys()),
            key="history_character",
        )
    conversation = _conversation_key(nhan_vat)
    audio_cache = st.session_state.history_audio_cache.setdefault(conversation, {})

    with col_voice:
        st.write("")
        st.write("")
        st.markdown(
            '<div class="audio-input-label compact"><i class="fa-solid fa-volume-high"></i>'
            '<span>Giọng đọc AI</span></div>',
            unsafe_allow_html=True,
        )
        bat_giong_noi = st.toggle("Bật giọng đọc", value=True, key="history_tts_toggle")
    with col_reset:
        st.write("")
        st.write("")
        icon_col, button_col = st.columns([0.22, 1])
        with icon_col:
            st.markdown('<div class="control-icon"><i class="fa-solid fa-rotate-right"></i></div>', unsafe_allow_html=True)
        with button_col:
            if st.button("Trò chuyện mới", key="clear_history_btn", width="stretch"):
                clear_messages(user_id, conversation)
                st.session_state.history_audio_cache[conversation] = {}
                st.session_state.mic_history_idx += 1
                st.rerun()

    messages = load_messages(user_id, conversation)
    for idx, msg in enumerate(messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            audio_data = audio_cache.get(idx)
            if audio_data:
                st.audio(audio_data, format="audio/mp3")

    st.markdown(
        '<div class="audio-input-label"><i class="fa-solid fa-microphone"></i>'
        '<span>Bấm Micro để trò chuyện bằng giọng nói:</span></div>',
        unsafe_allow_html=True,
    )
    audio_history = st.audio_input(
        " ",
        key=f"mic_history_{st.session_state.mic_history_idx}",
        label_visibility="collapsed",
    )
    prompt = st.chat_input(f"Gõ câu hỏi cho {nhan_vat}...", key="chat_input_history")

    if not (prompt or audio_history):
        return

    # Bản ghi âm đã được xử lý ở lượt này -> đổi key để lần chạy lại sau không gửi lại lần nữa
    audio_bytes_in = None
    if audio_history:
        if not prompt:
            audio_bytes_in = audio_history.getvalue()
        st.session_state.mic_history_idx += 1

    allowed, usage_id = consume_chat_quota(user_id)
    if not allowed:
        st.warning(f"Bạn đã sử dụng hết {MAX_DAILY_CHATS} lượt hỏi AI hôm nay.")
        return

    if prompt:
        user_text = prompt
        api_messages = messages + [{"role": "user", "content": prompt}]
    else:
        user_text = f"{VOICE_PREFIX} *Đang lắng nghe câu hỏi của quý khách...*"
        api_messages = messages

    with st.chat_message("user"):
        st.markdown(user_text)

    with st.chat_message("assistant"):
        with st.spinner(f"{nhan_vat} đang hồi đáp..."):
            result = fetch_gemini_reply(
                messages=api_messages,
                system_instruction=HISTORICAL_PROMPTS[nhan_vat],
                temperature=0.7,
                audio_bytes=audio_bytes_in,
                persona=True,
            )
        if not result.ok:
            # AI không trả lời được: hoàn lượt hỏi, không lưu thông báo lỗi vào lịch sử chat
            refund_chat_quota(usage_id)
            st.warning(result.text)
            return
        reply = st.write_stream(stream_text_smoothly(result.text))

        audio_bytes_out = None
        if bat_giong_noi and reply:
            with st.spinner("Đang tạo giọng đọc..."):
                audio_bytes_out = text_to_speech_vi(str(reply))
            if audio_bytes_out:
                st.audio(audio_bytes_out, format="audio/mp3", autoplay=True)

    if prompt:
        saved_user_msg = prompt
    elif result.transcript:
        saved_user_msg = f"{VOICE_PREFIX} {result.transcript}"
    else:
        saved_user_msg = f"{VOICE_PREFIX} Du khách đã gửi câu hỏi bằng giọng nói; bản chép lời chưa khả dụng."

    save_chat_turn(user_id, conversation, saved_user_msg, str(reply))
    if audio_bytes_out:
        # Vị trí tin nhắn trả lời = số tin cũ + 1 (câu hỏi vừa lưu đứng trước nó)
        audio_cache[len(messages) + 1] = audio_bytes_out
    # Không gọi st.rerun() ở đây để giọng đọc đang tự phát không bị ngắt giữa chừng.
    # Câu hỏi đã chép thành chữ sẽ hiện ở lần tương tác tiếp theo.
