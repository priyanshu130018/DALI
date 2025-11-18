import unittest
from unittest.mock import patch

import main as dali_main


class TestMainIntegration(unittest.TestCase):
    @patch("main.has_internet", return_value=False)
    @patch("main.is_cloud_available", return_value=False)
    def test_mode_switch_offline(self, *_):
        va = dali_main.VoiceAssistant()
        self.assertFalse(va.cloud_available)

    @patch("main.has_internet", return_value=True)
    @patch("main.is_cloud_available", return_value=True)
    def test_mode_switch_online(self, *_):
        va = dali_main.VoiceAssistant()
        self.assertTrue(va.cloud_available)


if __name__ == "__main__":
    unittest.main()