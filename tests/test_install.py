"""
Unit tests for install.py's pure-logic helpers (selection parsing).
Run from the repo root: python -m unittest discover -s tests -t .
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import install  # noqa: E402


class TestParseSelection(unittest.TestCase):
    def test_all(self):
        self.assertEqual(install.parse_selection("all", 5), {1, 2, 3, 4, 5})

    def test_none_and_empty(self):
        self.assertEqual(install.parse_selection("none", 5), set())
        self.assertEqual(install.parse_selection("", 5), set())

    def test_single_numbers(self):
        self.assertEqual(install.parse_selection("1,3,5", 5), {1, 3, 5})

    def test_range(self):
        self.assertEqual(install.parse_selection("2-4", 5), {2, 3, 4})

    def test_mixed(self):
        self.assertEqual(install.parse_selection("1,3-5", 5), {1, 3, 4, 5})

    def test_out_of_bounds_is_dropped(self):
        self.assertEqual(install.parse_selection("1,99", 5), {1})


class TestFuzzyScore(unittest.TestCase):
    def test_exact_substring_beats_scattered_match(self):
        exact = install._fuzzy_score("docker", "docker-development")
        scattered = install._fuzzy_score("docker", "do not check kernel driver")
        self.assertIsNotNone(exact)
        self.assertIsNotNone(scattered)
        self.assertLess(exact, scattered)

    def test_no_match_returns_none(self):
        self.assertIsNone(install._fuzzy_score("xyz123", "docker-development"))

    def test_typo_tolerance(self):
        # missing the 'e' in docker
        self.assertIsNotNone(install._fuzzy_score("dockr", "docker-development"))


class TestItemScore(unittest.TestCase):
    def _item(self, name, description):
        return {"name": name, "description": description}

    def test_name_match_beats_description_only_match(self):
        item_a = self._item("docker-patterns", "container tooling")
        item_b = self._item("unrelated-skill", "this one mentions docker in passing")
        score_a = install._item_score(["docker"], item_a)
        score_b = install._item_score(["docker"], item_b)
        self.assertLess(score_a, score_b)

    def test_multi_word_requires_all_words(self):
        item = self._item("docker-compose-helper", "Docker Compose patterns")
        self.assertIsNotNone(install._item_score(["docker", "compose"], item))
        self.assertIsNone(install._item_score(["docker", "kubernetes"], item))

    def test_description_does_not_fuzzy_match_prose_by_chance(self):
        # Regression test: pure subsequence matching against a full
        # description (not just a substring check) let common letters like
        # d-o-c-k-e-r match almost any long paragraph by coincidence, which
        # surfaced completely unrelated items for a real "docker k8s" query
        # during manual testing. Descriptions must use a real substring
        # check, not fuzzy subsequence matching.
        unrelated = self._item(
            "email-template-builder",
            "Build complete transactional email systems: React Email templates, provider integration",
        )
        self.assertIsNone(install._item_score(["docker"], unrelated))


if __name__ == "__main__":
    unittest.main()
