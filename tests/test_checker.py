import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "check.py"


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mirage-checker-test-")
        self.root = Path(self.temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)

    def tearDown(self):
        self.temporary.cleanup()

    def check(self):
        subprocess.run(["git", "add", "-f", "."], cwd=self.root, check=True, capture_output=True)
        return subprocess.run([sys.executable, str(CHECKER)], cwd=self.root, capture_output=True, text=True)

    def test_good_repository_and_broken_markdown(self):
        readme = self.root / "README.md"
        readme.write_text("[Guide](guide.md)\n")
        (self.root / "guide.md").write_text("# Guide\n")
        self.assertEqual(self.check().returncode, 0)
        readme.write_text("[Guide](missing.md)\n")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("relative Markdown target", result.stderr)

    def test_sensitive_file_and_assignment_hide_values(self):
        value = "DO_NOT_DISCLOSE_THIS_FIXTURE"
        (self.root / ".env").write_text("TOKEN=" + value + "\n")
        (self.root / "settings.json").write_text('{"TOKEN": "' + value + '"}\n')
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("sensitive filename", result.stderr)
        self.assertIn("credential-like assignment", result.stderr)
        self.assertNotIn(value, result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
