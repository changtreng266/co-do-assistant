"""
Module: services/gemini_service.py
Chức năng:
    - Kết nối tới ShopAIKey Gateway qua chuẩn OpenAI Compatible (/v1/chat/completions).
    - Tự động chuyển sang model dự phòng (Fallback) nếu model chính bị Rate Limit (429) hoặc quá tải.
    - Hỗ trợ đầy đủ lịch sử hội thoại nối tiếp từ SQLite, Micro (input_audio) và TTS tiếng Việt.
"""

import base64
import io
import json
import logging
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from gtts import gTTS

from config.settings import get_api_key, get_base_url, get_model_name

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VOICE_PREFIX = "🎙️"
_LEGACY_VOICE_PLACEHOLDER = "🎙️ *["

# Danh sách model có thật trên ShopAIKey dùng làm dự phòng theo thứ tự ưu tiên
FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gpt-4.1-mini",
    "gpt-4o-mini",
    "deepseek-v4-flash",
]


@dataclass
class GeminiResult:
    text: str
    ok: bool
    transcript: str | None = None


def build_openai_messages(messages: list[dict], system_instruction: str) -> list[dict]:
    """Chuyển lịch sử tin nhắn từ SQLite sang định dạng messages chuẩn OpenAI."""
    result: list[dict] = []
    if system_instruction and system_instruction.strip():
        result.append({"role": "system", "content": system_instruction.strip()})

    for msg in messages:
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue
        content = str(msg.get("content", "") or "").strip()
        if not content or content.startswith(_LEGACY_VOICE_PLACEHOLDER):
            continue
        if content.startswith(VOICE_PREFIX):
            content = content[len(VOICE_PREFIX):].strip()
            if not content:
                continue
        if result and result[-1]["role"] == role:
            result[-1]["content"] += "\n" + content
        else:
            result.append({"role": role, "content": content})

    return result


def _classify_error(status_code: int, err_msg: str) -> str:
    m = err_msg.upper()
    if status_code in (401, 403) or "INVALID_API_KEY" in m or "UNAUTHORIZED" in m:
        return "auth"
    if status_code == 404 or "MODEL_NOT_FOUND" in m or "DOES NOT EXIST" in m:
        return "model"
    if status_code == 429 or "RATE_LIMIT" in m or "QUOTA" in m or "INSUFFICIENT_QUOTA" in m:
        return "quota"
    if status_code == 400 or "INVALID_REQUEST" in m:
        return "bad_request"
    return "busy"


def _busy_reply(messages: list[dict], persona: bool) -> str:
    if persona:
        return (
            "Chào quý khách phương xa! Hiện đường truyền tới kinh thành đang quá tải lượt người ghé thăm, "
            "xin quý khách vui lòng gửi lại lời nhắn sau vài giây để ta tiếp tục đàm đạo nhé!"
        )
    last_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_msg = m.get("content", "").strip().lower()
            break
    greetings = ("alo", "hi", "hello", "chào", "xin chào", "test", "có ai không")
    if len(last_msg) <= 15 and any(g in last_msg for g in greetings):
        return (
            "Xin chào quý khách! 👋 Tôi là **Hướng dẫn viên Du lịch AI Cố Đô**.\n\n"
            "Hiện máy chủ AI đang hơi đông, nhưng tôi vẫn sẵn sàng hỗ trợ bạn lên lịch trình "
            "**Hà Nam - Nam Định - Ninh Bình**. Bạn vui lòng gửi lại câu hỏi sau vài giây nhé!"
        )
    return "Máy chủ AI đang tạm thời quá tải. Quý khách vui lòng chờ **3–5 giây** rồi gửi lại câu hỏi nhé!"


def _error_message(kind: str, messages: list[dict], persona: bool, model_name: str, base_url: str) -> str:
    if kind == "auth":
        return f"⚠️ API key không hợp lệ hoặc hết số dư. Kiểm tra `GEMINI_API_KEY` và `GEMINI_BASE_URL` (`{base_url}`)."
    if kind == "model":
        return f"⚠️ Không tìm thấy model `{model_name}` trên `{base_url}`. Kiểm tra lại `GEMINI_MODEL` trong `secrets.toml`."
    if kind == "quota":
        return "⏳ Các cụm máy chủ AI đều đang chạm giới hạn tần suất (Rate Limit). Vui lòng thử lại sau vài giây."
    if kind == "bad_request":
        return "⚠️ Yêu cầu gửi tới AI không hợp lệ (có thể model hiện tại chưa hỗ trợ đầu vào âm thanh Micro). Hãy thử gõ chữ nhé!"
    return _busy_reply(messages, persona)


def _parse_voice_response(raw: str) -> tuple[str, str | None]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)
    try:
        data = json.loads(cleaned)
        answer = str(data.get("tra_loi", "")).strip()
        question = str(data.get("cau_hoi", "")).strip() or None
        if answer:
            return answer, question
    except (json.JSONDecodeError, AttributeError):
        pass
    return raw.strip(), None


def fetch_gemini_reply(
    messages: list[dict],
    system_instruction: str,
    temperature: float = 0.6,
    audio_bytes: bytes | None = None,
    persona: bool = False,
) -> GeminiResult:
    """Gửi yêu cầu tới ShopAIKey Gateway qua /v1/chat/completions kèm tự động đổi model dự phòng."""
    api_key = get_api_key()
    if not api_key or api_key == "DAN_API_KEY_GEMINI_CUA_BAN_VAO_DAY":
        return GeminiResult("⚠️ Chưa cấu hình `GEMINI_API_KEY` hợp lệ trong `.streamlit/secrets.toml`.", ok=False)

    base_url = get_base_url()
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    endpoint = f"{base_url}/chat/completions"

    primary_model = get_model_name()
    candidate_models = [primary_model] + [m for m in FALLBACK_MODELS if m != primary_model]

    chat_messages = build_openai_messages(messages, system_instruction)
    if audio_bytes:
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
        chat_messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Hãy nghe câu hỏi tiếng Việt của du khách trong đoạn âm thanh này và trả lời dựa trên ngữ cảnh "
                            "cuộc trò chuyện trước đó. Chỉ trả về JSON hợp lệ gồm 2 khóa: "
                            "'cau_hoi' (câu hỏi chép lại nguyên văn bằng chữ) và 'tra_loi' (câu trả lời chi tiết bằng Markdown)."
                        ),
                    },
                    {
                        "type": "input_audio",
                        "input_audio": {"data": audio_b64, "format": "wav"},
                    },
                ],
            }
        )

    error_kind = "busy"
    last_tried_model = primary_model

    for idx, model_name in enumerate(candidate_models):
        last_tried_model = model_name
        payload = {
            "model": model_name,
            "messages": chat_messages,
            "temperature": max(0.0, min(float(temperature), 1.0)),
            "max_tokens": 4096,
        }
        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(
            endpoint,
            data=body_bytes,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "CoDoAI-Streamlit/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw_resp = resp.read().decode("utf-8")
                data = json.loads(raw_resp)
                choices = data.get("choices") or []
                text = ""
                if choices:
                    msg_obj = choices[0].get("message") or {}
                    text = str(msg_obj.get("content") or "").strip()

                if text:
                    logger.info(f"[AI OK] {model_name} phản hồi thành công (lần thử {idx + 1})")
                    if audio_bytes:
                        answer, question = _parse_voice_response(text)
                        return GeminiResult(answer, ok=True, transcript=question)
                    return GeminiResult(text, ok=True)
                error_kind = "busy"

        except urllib.error.HTTPError as http_err:
            err_body = ""
            try:
                err_body = http_err.read().decode("utf-8", errors="ignore")
            except Exception:
                pass
            logger.warning(f"[AI Fallback {idx + 1}/{len(candidate_models)}] {model_name} -> HTTP {http_err.code}: {err_body[:200]}")
            error_kind = _classify_error(http_err.code, err_body)
            if error_kind == "auth":
                break
        except Exception as err:
            logger.warning(f"[AI Fallback {idx + 1}/{len(candidate_models)}] {model_name} lỗi ({type(err).__name__}): {err}")
            error_kind = "busy"

        if idx < len(candidate_models) - 1:
            time.sleep(0.5)

    return GeminiResult(_error_message(error_kind, messages, persona, last_tried_model, base_url), ok=False)


def stream_text_smoothly(full_text: str):
    """Generator chia nhỏ văn bản thành từng từ để hiển thị hiệu ứng gõ chữ trên Streamlit."""
    words = full_text.split(" ")
    for i, word in enumerate(words):
        yield word + (" " if i < len(words) - 1 else "")
        time.sleep(0.015)


def text_to_speech_vi(text: str) -> bytes | None:
    """Chuyển đổi văn bản câu trả lời thành tệp âm thanh giọng đọc tiếng Việt (MP3)."""
    try:
        clean_text = text.replace("*", "").replace("#", "").replace("-", " ")
        tts = gTTS(text=clean_text, lang="vi")
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp.read()
    except Exception as err:
        logger.error(f"[TTS Error]: {err}")
        return None