import unittest
from unittest.mock import patch, MagicMock

import offline.wake_word as ww


class TestWakeWord(unittest.TestCase):
    @patch("offline.wake_word.os.path.exists", return_value=False)
    def test_missing_file(self, _):
        with self.assertRaises(FileNotFoundError):
            ww.WakeWordDetector(lambda: None)


if __name__ == "__main__":
    unittest.main()