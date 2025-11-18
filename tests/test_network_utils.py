import unittest
from unittest.mock import patch

from online.network_utils import has_internet, is_cloud_available


class TestNetworkUtils(unittest.TestCase):
    @patch("online.network_utils.requests.get")
    def test_has_internet(self, mock_get):
        mock_get.return_value.status_code = 204
        self.assertTrue(has_internet())

    @patch("online.network_utils.requests.post")
    def test_is_cloud_available_no_key(self, mock_post):
        # Without key configured, function should return False
        self.assertFalse(is_cloud_available())


if __name__ == "__main__":
    unittest.main()