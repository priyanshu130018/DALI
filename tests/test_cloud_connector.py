import unittest
from unittest.mock import patch, Mock

import online.cloud_connector as cc


class TestCloudConnector(unittest.TestCase):
    @patch("online.cloud_connector.requests.post")
    def test_get_cloud_response_basic(self, mock_post):
        cc.SARVAM_API_KEY = "abc"
        mock_post.return_value = Mock(status_code=200)
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "Hello"}}]
        }
        text = cc.get_cloud_response("hi")
        self.assertEqual(text, "Hello")

    @patch("online.cloud_connector.requests.post")
    def test_transcribe_audio(self, mock_post):
        cc.SARVAM_API_KEY = "abc"
        mock_post.return_value = Mock(status_code=200)
        mock_post.return_value.json.return_value = {
            "transcript": "hello",
            "language_code": "en-IN",
        }
        t, lang = cc.transcribe_audio(b"abc")
        self.assertEqual(t, "hello")
        self.assertEqual(lang, "en-IN")


if __name__ == "__main__":
    unittest.main()