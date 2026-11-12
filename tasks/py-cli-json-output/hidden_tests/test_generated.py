"""Hidden check: generated lockfiles (see scripts/make_lockscan_task.py).

Text invocations must reproduce the original tool's output byte for byte; JSON
invocations must match documents computed independently from the generator's data.
"""

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from lockscan.cli import main

CASES = json.loads((Path(__file__).parent / "cases.json").read_text())


def run_inproc(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class TestGenerated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="lockscan-hidden-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_cases(self):
        for k, case in enumerate(CASES):
            path = self.tmp / f"case{k}.lock"
            path.write_text(case["lockfile"])
            for r in case["runs"]:
                with self.subTest(case=k, args=r["args"]):
                    code, out, err = run_inproc(["-f", str(path), *r["args"]])
                    if "json" in r:
                        self.assertEqual(err, "")
                        self.assertEqual(code, r["code"])
                        self.assertTrue(out.endswith("\n"))
                        self.assertEqual(json.loads(out), r["json"])
                    else:
                        self.assertEqual((code, out, err), (r["code"], r["stdout"], r["stderr"]))
                        if r["args"][0] in ("licenses", "check"):
                            again = run_inproc(["-f", str(path), *r["args"], "--format", "text"])
                            self.assertEqual(again, (code, out, err))


BAD = {
    "parse_error": ["version = 1\n[[package]\n", b"version = 1\nname = \"\xff\"\n"],
    "invalid_lockfile": [
        "version = 2\n",
        "version = 1\n[[package]]\nname = \"a\"\n",
        "version = 1\n[[package]]\nname = \"a\"\nversion = \"1.x\"\n",
        "version = 1\n[[package]]\nname = \"a\"\nversion = \"1\"\ndependencies = [\"b >> 2\"]\n",
        "version = 1\n[[package]]\nname = \"a\"\nversion = \"1\"\nsource = \"ftp\"\n",
        "version = 1\n[[package]]\nname = \"a\"\nversion = \"1\"\n"
        "[[package]]\nname = \"a\"\nversion = \"1.0\"\n",
        "version = 1\n[project]\ndependencies = []\n",
    ],
}


class TestErrors(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lockscan-err-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def check_error(self, path, code_name):
        for command in (["licenses"], ["check", "--strict"], ["licenses", "--only-direct"]):
            with self.subTest(path=path.name, command=command):
                t_code, t_out, t_err = run_inproc(["-f", str(path), *command])
                self.assertEqual((t_code, t_out), (2, ""))
                self.assertTrue(t_err.startswith("lockscan: error: "))
                message = t_err[len("lockscan: error: "):].rstrip("\n")
                j_code, j_out, j_err = run_inproc(["-f", str(path), *command, "--format", "json"])
                self.assertEqual((j_code, j_err), (3, ""))
                self.assertEqual(json.loads(j_out),
                                 {"error": {"code": code_name, "message": message}})

    def test_read_error(self):
        self.check_error(self.tmp / "missing.lock", "read_error")
        self.check_error(self.tmp, "read_error")  # a directory

    def test_bad_lockfiles(self):
        for code_name, contents in BAD.items():
            for k, content in enumerate(contents):
                path = self.tmp / f"{code_name}{k}.lock"
                if isinstance(content, bytes):
                    path.write_bytes(content)
                else:
                    path.write_text(content)
                self.check_error(path, code_name)

    def test_format_only_on_two_commands(self):
        path = self.tmp / "ok.lock"
        path.write_text("version = 1\n")
        for command in (["summary"], ["tree"], ["why", "x"]):
            with self.subTest(command=command):
                code, out, _ = run_inproc(["-f", str(path), *command, "--format", "json"])
                self.assertEqual((code, out), (2, ""))

    def test_usage_errors_unchanged(self):
        code, out, err = run_inproc(["check", "--format", "xml"])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("invalid choice", err)


if __name__ == "__main__":
    unittest.main()
