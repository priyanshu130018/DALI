import unittest
from unittest.mock import patch, MagicMock

import offline.tts_engine as tts


class TestTTSEngine(unittest.TestCase):
    @patch("offline.tts_engine.pyttsx3")
    def test_speak_queue(self, mock_tts):
        mock_engine = MagicMock()
        mock_tts.init.return_value = mock_engine
        tts.speak("hello", wait=True)
        self.assertTrue(tts.speech_complete.is_set())


if __name__ == "__main__":
    unittest.main()