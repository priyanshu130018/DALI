import unittest
from agents.realtime import RealtimeAgent


class TestRealtimeAgent(unittest.TestCase):
    def test_cache_basic(self):
        agent = RealtimeAgent()
        # Directly set cache and retrieve
        agent.cache.set("weather:default", "Current weather: 25°C Clear")
        self.assertEqual(agent.cache.get("weather:default"), "Current weather: 25°C Clear")


if __name__ == "__main__":
    unittest.main()