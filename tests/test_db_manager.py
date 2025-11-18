import os
import unittest

from database.db_manager import DBManager


class TestDBManager(unittest.TestCase):
    def test_sqlite_insert_and_fetch(self):
        # Ensure MySQL vars are unset for SQLite
        for k in ["MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DB"]:
            os.environ.pop(k, None)
        db = DBManager()
        conv_id = db.insert_conversation(
            user_text="hello",
            response_text="hi",
            mode="offline",
            language="en-IN",
            metadata={"test": True},
        )
        self.assertIsInstance(conv_id, int)
        row = db.get_conversation(conv_id)
        self.assertIsNotNone(row)
        db.delete_conversation(conv_id)
        db.close()


if __name__ == "__main__":
    unittest.main()