"""
Unit tests for catalog/llm_review.py — the LLM-response JSON extraction
(models frequently wrap JSON in markdown fences despite instructions not to).

Run from the repo root:
    python -m unittest discover -s tests -t .
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from catalog import llm_review  # noqa: E402


class TestExtractJson(unittest.TestCase):
    def test_plain_json(self):
        result = llm_review._extract_json('{"verdict": "safe", "confidence": 0.9, "reasoning": "fine"}')
        self.assertEqual(result["verdict"], "safe")

    def test_markdown_fenced_json(self):
        raw = '```json\n{"verdict": "suspicious", "confidence": 0.5, "reasoning": "hmm"}\n```'
        result = llm_review._extract_json(raw)
        self.assertEqual(result["verdict"], "suspicious")

    def test_json_with_surrounding_prose(self):
        raw = 'Here is my analysis:\n{"verdict": "malicious", "confidence": 0.8, "reasoning": "bad"}\nHope that helps!'
        result = llm_review._extract_json(raw)
        self.assertEqual(result["verdict"], "malicious")

    def test_no_json_raises(self):
        with self.assertRaises(json.JSONDecodeError):
            llm_review._extract_json("no json here at all")


if __name__ == "__main__":
    unittest.main()
