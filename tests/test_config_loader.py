import os
import unittest

from utils.config import load_config


class TestConfigLoader(unittest.TestCase):
    def test_env_substitution(self):
        os.environ["PICOVOICE_ACCESS_KEY"] = "TESTKEY"
        cfg = load_config()
        self.assertEqual(cfg["keys"]["picovoice"], "TESTKEY")


if __name__ == "__main__":
    unittest.main()