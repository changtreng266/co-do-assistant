"""Kiểm thử helper AI Gateway (ShopAIKey / OpenAI-Compatible) mà không gọi API thật hoặc tiêu tốn quota."""
import io
import json
import unittest
from unittest.mock import MagicMock, patch

from services import gemini_service as gemini


class GeminiServiceTests(unittest.TestCase):
    def test_error_classification(self):
        self.assertEqual(gemini._classify_error(403, "PERMISSION_DENIED"), "auth")
        self.assertEqual(gemini._classify_error(404, "MODEL_NOT_FOUND"), "model")
        self.assertEqual(gemini._classify_error(429, "RATE_LIMIT_EXCEEDED"), "quota")

    def test_parse_voice_json(self):
        answer, transcript = gemini._parse_voice_response(
            '{"cau_hoi":"Tôi muốn đi đâu?","tra_loi":"Bạn có thể thăm Hoa Lư."}'
        )
        self.assertEqual(answer, "Bạn có thể thăm Hoa Lư.")
        self.assertEqual(transcript, "Tôi muốn đi đâu?")

    def test_history_merges_adjacent_roles_and_strips_voice_prefix(self):
        history = gemini.build_openai_messages(
            [
                {"role": "user", "content": "🎙️ Xin chào"},
                {"role": "user", "content": "Tôi muốn đến Hoa Lư"},
                {"role": "assistant", "content": "Bạn có thể đi vào buổi sáng."},
            ],
            "Bạn là hướng dẫn viên",
        )
        self.assertEqual([item["role"] for item in history], ["system", "user", "assistant"])
        self.assertEqual(history[1]["content"], "Xin chào\nTôi muốn đến Hoa Lư")

    @patch.object(gemini, "get_base_url", return_value="https://api.shopaikey.com/v1")
    @patch.object(gemini, "get_model_name", return_value="gemini-3.8-flash")
    @patch.object(gemini, "get_api_key", return_value="test-key")
    @patch("services.gemini_service.urllib.request.urlopen")
    def test_fetch_text_reply_with_mocked_provider(self, mock_urlopen, _key, _model, _url):
        fake_payload = json.dumps({"choices": [{"message": {"content": "Xin chào du khách!"}}]}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_payload
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = gemini.fetch_gemini_reply(
            [{"role": "user", "content": "Xin chào"}], "Bạn là hướng dẫn viên"
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.text, "Xin chào du khách!")


if __name__ == "__main__":
    unittest.main()