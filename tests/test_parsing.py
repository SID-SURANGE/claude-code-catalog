"""
Unit tests for catalog/parsing.py — frontmatter parsing, content scoring,
and category classification.

Run from the repo root:
    python -m unittest discover -s tests -t .
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from catalog import parsing  # noqa: E402


class TestParseFrontmatter(unittest.TestCase):
    def test_simple_fields(self):
        text = '---\nname: my-skill\ndescription: does a thing\n---\nBody text.'
        fm = parsing.parse_frontmatter(text)
        self.assertEqual(fm["name"], "my-skill")
        self.assertEqual(fm["description"], "does a thing")

    def test_block_scalar_description(self):
        # Real-world bug this was fixing: a naive line-splitter treats the
        # `|` on its own line as the literal value instead of a YAML block
        # scalar indicator for the indented lines that follow.
        text = (
            "---\n"
            "name: agent-creator\n"
            "description: |\n"
            "  Use this agent when the user asks to create an agent.\n"
            "  Handles scaffolding and validation.\n"
            "---\n"
            "Body.\n"
        )
        fm = parsing.parse_frontmatter(text)
        self.assertNotEqual(fm["description"], "|")
        self.assertIn("create an agent", fm["description"])
        self.assertIn("scaffolding", fm["description"])

    def test_no_frontmatter_returns_empty(self):
        self.assertEqual(parsing.parse_frontmatter("just a plain file\nwith no fences"), {})


class TestScoreContent(unittest.TestCase):
    def test_placeholder_is_penalized(self):
        score, signals = parsing.score_content("", "TODO", False)
        self.assertLess(score, 0)
        self.assertIn("placeholder/stub content", signals)

    def test_substantive_content_scores_higher(self):
        desc = "A genuinely useful skill that does something specific and non-trivial."
        body = "## Usage\n\n" + ("word " * 200) + "\n```bash\necho hi\n```"
        score, signals = parsing.score_content(desc, body, has_extra_files=True)
        self.assertGreater(score, 1.5)
        self.assertIn("has usage/example section", signals)
        self.assertIn("has code block", signals)
        self.assertIn("bundles extra files", signals)

    def test_short_stub_scores_lower_than_full_skill(self):
        stub_score, _ = parsing.score_content("x", "short", False)
        full_score, _ = parsing.score_content(
            "A real, substantive description of what this does and why.",
            "## Example\n\n" + ("detailed instructions " * 100),
            True,
        )
        self.assertLess(stub_score, full_score)


class TestCategoryForPath(unittest.TestCase):
    def test_skill_md(self):
        self.assertEqual(parsing.category_for_path(Path("foo/bar/SKILL.md")), "skill")

    def test_agent_dir(self):
        self.assertEqual(parsing.category_for_path(Path("plugins/x/agents/my-agent.md")), "agent")

    def test_unrelated_path(self):
        self.assertIsNone(parsing.category_for_path(Path("docs/readme.md")))


if __name__ == "__main__":
    unittest.main()
