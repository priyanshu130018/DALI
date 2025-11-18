import unittest
from unittest.mock import patch, MagicMock

import offline.recognizer as rec


class TestRecognizer(unittest.TestCase):
    @patch("offline.recognizer.vosk")
    @patch("offline.recognizer.pyaudio.PyAudio")
    def test_init_model(self, mock_pa, mock_vosk):
        mock_vosk.Model.return_value = MagicMock()
        r = rec.Recognizer()
        self.assertIsNotNone(r.model)


if __name__ == "__main__":
    unittest.main()