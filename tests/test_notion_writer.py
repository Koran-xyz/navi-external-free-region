import os
import unittest
from unittest.mock import patch

from src.notion_writer import NotionWriterError, build_payload, validate_record


GOOD = {
    "record_name": "テスト記録",
    "actor": "ゴテン",
    "summary": "外部自由領域の書き込みテスト",
    "evidence": "入力形式を確認",
    "result": "新規追記のみ",
    "next_action": "次のAIへ引き継ぐ",
    "status": "進行中",
}


class NotionWriterTests(unittest.TestCase):
    def test_required_fields(self):
        bad = dict(GOOD)
        bad["evidence"] = ""
        with self.assertRaises(NotionWriterError):
            validate_record(bad)

    def test_sensitive_data_is_blocked(self):
        bad = dict(GOOD)
        bad["summary"] = "住所を記録する"
        with self.assertRaises(NotionWriterError):
            validate_record(bad)

    def test_payload_uses_data_source_from_environment(self):
        with patch.dict(os.environ, {"NOTION_DATA_SOURCE_ID": "test-data-source"}):
            payload = build_payload(GOOD)
        self.assertEqual(payload["parent"]["data_source_id"], "test-data-source")
        self.assertEqual(payload["properties"]["記録名"]["title"][0]["text"]["content"], "テスト記録")


if __name__ == "__main__":
    unittest.main()
