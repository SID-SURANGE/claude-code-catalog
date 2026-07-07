"""
Unit tests for the first-party quality hooks' pure logic, plus an
end-to-end stdin smoke test per hook (synthetic hook-input JSON in,
exit 0 and well-formed-or-empty output back).
Run from the repo root: python -m unittest discover -s tests -t .
"""
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
HOOKS = ROOT / "first-party" / "hooks"


def load(name):
    """Import a hook module despite the dash in its filename."""
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), HOOKS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


test_integrity = load("test-integrity")
completion_verifier = load("completion-verifier")
structure_sentry = load("structure-sentry")
claim_checker = load("claim-checker")


class TestTestIntegrityCompare(unittest.TestCase):
    def test_deleted_assertion_flagged(self):
        old = "def test_x():\n    assert a == 1\n    assert b == 2\n"
        new = "def test_x():\n    assert a == 1\n"
        findings = test_integrity.compare(old, new)
        self.assertTrue(any("assertion count dropped" in f for f in findings))

    def test_added_skip_flagged(self):
        old = "def test_x():\n    assert a == 1\n"
        new = "@pytest.mark.skip\ndef test_x():\n    assert a == 1\n"
        findings = test_integrity.compare(old, new)
        self.assertTrue(any("skip/only marker added" in f for f in findings))

    def test_js_only_flagged(self):
        old = "it('works', () => { expect(x).toEqual(1) })"
        new = "it.only('works', () => { expect(x).toEqual(1) })"
        findings = test_integrity.compare(old, new)
        self.assertTrue(any("skip/only" in f for f in findings))

    def test_loosened_equality_flagged(self):
        old = "expect(result).toEqual({a: 1})"
        new = "expect(result).toBeDefined()"
        findings = test_integrity.compare(old, new)
        self.assertTrue(any("loosened" in f for f in findings))

    def test_commented_out_assert_flagged(self):
        old = "    assert x == 1\n"
        new = "    # assert x == 1\n    assert True\n"
        findings = test_integrity.compare(old, new)
        self.assertTrue(any("commented out" in f for f in findings))

    def test_clean_edit_is_silent(self):
        old = "def test_x():\n    assert a == 1\n"
        new = "def test_x():\n    assert a == 1\n    assert b == 2\n"
        self.assertEqual(test_integrity.compare(old, new), [])

    def test_non_test_paths_ignored_by_regex(self):
        self.assertIsNone(test_integrity.TEST_FILE_RE.search("src/app/main.py"))
        self.assertIsNotNone(test_integrity.TEST_FILE_RE.search("tests/test_parsing.py"))
        self.assertIsNotNone(test_integrity.TEST_FILE_RE.search("src/foo.spec.ts"))


class TestCompletionVerifierParsing(unittest.TestCase):
    DIFF = (
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -10,0 +11,3 @@\n"
        "+def new_feature():\n"
        "+    # TODO: handle the error path\n"
        "+    raise NotImplementedError\n"
    )

    def test_added_lines_positions(self):
        lines = list(completion_verifier.parse_added_lines(self.DIFF))
        self.assertEqual(lines[0], ("app.py", 11, "def new_feature():"))
        self.assertEqual(lines[2][1], 13)

    def test_stub_patterns_match(self):
        hits = []
        for _, _, text in completion_verifier.parse_added_lines(self.DIFF):
            for pattern, label in completion_verifier.STUB_PATTERNS:
                if pattern.search(text):
                    hits.append(label)
                    break
        self.assertIn("leftover TODO/FIXME marker", hits)
        self.assertIn("raises NotImplementedError", hits)

    def test_removed_lines_ignored(self):
        diff = self.DIFF.replace("+    # TODO", "-    # TODO")
        texts = [t for _, _, t in completion_verifier.parse_added_lines(diff)]
        self.assertNotIn("    # TODO: handle the error path", texts)


class TestStructureSentryChecks(unittest.TestCase):
    def test_duplicate_stem_detected(self):
        from pathlib import PurePosixPath
        finding = structure_sentry.check_duplicate_stem(
            PurePosixPath("src/api/helpers.py"), ["src/core/helpers.py", "src/core/db.py"]
        )
        self.assertIn("already exists", finding)

    def test_generic_stems_exempt(self):
        from pathlib import PurePosixPath
        finding = structure_sentry.check_duplicate_stem(
            PurePosixPath("src/api/__init__.py"), ["src/core/__init__.py"]
        )
        self.assertIsNone(finding)

    def test_source_in_test_dir_flagged(self):
        from pathlib import PurePosixPath
        finding = structure_sentry.check_layer(PurePosixPath("tests/database.py"))
        self.assertIn("tests directory", finding)
        self.assertIsNone(structure_sentry.check_layer(PurePosixPath("tests/test_db.py")))
        self.assertIsNone(structure_sentry.check_layer(PurePosixPath("tests/conftest.py")))

    def test_new_top_level_dir_flagged(self):
        from pathlib import PurePosixPath
        tracked = ["src/a.py", "tests/test_a.py"]
        finding = structure_sentry.check_new_top_dir(PurePosixPath("utilities/b.py"), tracked)
        self.assertIn("new top-level directory", finding)
        self.assertIsNone(structure_sentry.check_new_top_dir(PurePosixPath("src/b.py"), tracked))


class TestClaimChecker(unittest.TestCase):
    @staticmethod
    def _transcript(final_text, commands=(), errored=False):
        entries = [
            {"type": "user", "message": {"content": "please fix the parser"}},
        ]
        for i, cmd in enumerate(commands):
            entries.append({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "id": f"t{i}", "input": {"command": cmd}},
            ]}})
            entries.append({"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": f"t{i}", "is_error": errored},
            ]}})
        entries.append({"type": "assistant", "message": {"content": [{"type": "text", "text": final_text}]}})
        return entries

    def test_unbacked_test_claim_flagged(self):
        findings = claim_checker.check(self._transcript("Done — all tests pass."))
        self.assertTrue(any("tests" in f for f in findings))

    def test_backed_test_claim_silent(self):
        findings = claim_checker.check(
            self._transcript("Done — all tests pass.", commands=["python -m pytest"])
        )
        self.assertEqual(findings, [])

    def test_errored_command_does_not_back_claim(self):
        findings = claim_checker.check(
            self._transcript("Done — all tests pass.", commands=["python -m pytest"], errored=True)
        )
        self.assertTrue(findings)

    def test_no_claim_is_silent(self):
        findings = claim_checker.check(self._transcript("I refactored the parser as requested."))
        self.assertEqual(findings, [])

    def test_only_current_turn_counts(self):
        entries = self._transcript("ok", commands=["python -m pytest"])
        entries.append({"type": "user", "message": {"content": "now add a feature"}})
        entries.append({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Added. All tests pass."}
        ]}})
        findings = claim_checker.check(entries)
        self.assertTrue(findings, "pytest ran in a previous turn; the new claim is unbacked")


class TestHooksEndToEnd(unittest.TestCase):
    """Feed each hook synthetic stdin and require exit 0 + JSON-or-empty stdout."""

    def _run(self, script, payload):
        proc = subprocess.run(
            [sys.executable, str(HOOKS / script)],
            input=json.dumps(payload), capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        if proc.stdout.strip():
            out = json.loads(proc.stdout)
            self.assertIn("hookSpecificOutput", out)
        return proc.stdout.strip()

    def test_test_integrity_flags_weakened_edit(self):
        out = self._run("test-integrity.py", {
            "tool_name": "Edit", "cwd": str(ROOT),
            "tool_input": {
                "file_path": "tests/test_example.py",
                "old_string": "assert a == 1\nassert b == 2",
                "new_string": "assert a == 1",
            },
        })
        self.assertIn("test-integrity", out)

    def test_test_integrity_silent_on_non_test_file(self):
        out = self._run("test-integrity.py", {
            "tool_name": "Edit", "cwd": str(ROOT),
            "tool_input": {"file_path": "src/app.py", "old_string": "assert x", "new_string": ""},
        })
        self.assertEqual(out, "")

    def test_stop_hooks_silent_when_stop_hook_active(self):
        for script in ("completion-verifier.py", "claim-checker.py", "stop-gate-review.py"):
            out = self._run(script, {"stop_hook_active": True, "cwd": str(ROOT)})
            self.assertEqual(out, "", msg=script)

    def test_goal_anchor_silent_and_exits_zero(self):
        out = self._run("goal-anchor.py", {"session_id": "unittest", "prompt": "add a feature"})
        self.assertEqual(out, "")

    def test_hooks_survive_garbage_input(self):
        for script in ("test-integrity.py", "completion-verifier.py", "structure-sentry.py",
                       "claim-checker.py", "goal-anchor.py", "stop-gate-review.py"):
            proc = subprocess.run(
                [sys.executable, str(HOOKS / script)],
                input="not json at all", capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(proc.returncode, 0, msg=f"{script}: {proc.stderr}")


if __name__ == "__main__":
    unittest.main()
