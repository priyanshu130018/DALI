import unittest
from unittest.mock import patch, MagicMock

import offline.rasa_handler as rh


class TestRasaHandler(unittest.TestCase):
    @patch("offline.rasa_handler.Agent.load")
    @patch("offline.rasa_handler.os.path.exists", return_value=True)
    def test_init(self, _exists, mock_load):
        mock_agent = MagicMock()
        mock_agent.domain = MagicMock(intents=["tell_time"], action_names_or_texts=["action_tell_time"], intent_properties={})
        mock_load.return_value = mock_agent
        handler = rh.RasaHandler()
        self.assertIsNotNone(handler.agent)


if __name__ == "__main__":
    unittest.main()