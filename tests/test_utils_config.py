import os
import unittest

from utils.config import load_config, validate_env


class TestUtilsConfig(unittest.TestCase):
    def test_validate_env(self):
        os.environ["SARVAM_API_KEY"] = "sk_test"
        os.environ["PICOVOICE_ACCESS_KEY"] = "pk_test"
        cfg = load_config()
        flags = validate_env(cfg)
        self.assertTrue(flags["sarvam_configured"])
        self.assertTrue(flags["picovoice_configured"])


if __name__ == "__main__":
    unittest.main()