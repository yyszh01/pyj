import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

import importlib.util  # noqa: E402
import traceback  # noqa: E402

# Test the repository's pyj.py, not an installed copy (an installed pyj is imported at startup by its .pth)
PYJ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pyj.py"))
_spec = importlib.util.spec_from_file_location("pyj", PYJ)
_pyj = importlib.util.module_from_spec(_spec)
sys.path_hooks[:] = [h for h in sys.path_hooks if not getattr(h, "_pyj", False)]
sys.path_importer_cache.clear()
sys.modules["pyj"] = _pyj
_spec.loader.exec_module(_pyj)

from pyj import PyjSyntaxError, compile_pyj, transpile  # noqa: E402


def run(src):
    ns = {}
    exec(compile(transpile(src), "<test>", "exec"), ns)
    return ns


class TestTranspile(unittest.TestCase):
    def check(self, src, expected):
        self.assertEqual(transpile(src), textwrap.dedent(expected).lstrip("\n"))

    def test_one_line_block(self):
        self.check("if x { a(); b() }", """
            if x:
                a()
                b()
        """)

    def test_colon_optional(self):
        self.check("def f(x) -> int: { return x }", """
            def f(x) -> int:
                return x
        """)

    def test_else_if(self):
        self.check("if a {} else if b {} else {}", """
            if a:
                pass
            elif b:
                pass
            else:
                pass
        """)

    def test_set_in_header(self):
        self.check("if x in {1, 2} { y = {} }", """
            if x in {1, 2}:
                y = {}
        """)

    def test_asi_and_continuation(self):
        self.check("a = 1\nb = (2,\n 3)\nc = a and\n  b\nd = x\n  .strip()", """
            a = 1
            b = (2, 3)
            c = a and b
            d = x.strip()
        """)

    def test_brace_on_next_line(self):
        self.check("while True\n{\n break\n}", """
            while True:
                break
        """)

    def test_triple_string_kept(self):
        ns = run('s = """a\n  b"""; t = f"""{ {"k": 1}["k"] }\n"""')
        self.assertEqual(ns["s"], "a\n  b")
        self.assertEqual(ns["t"], "1\n")

    @unittest.skipIf(sys.version_info < (3, 12), "reusing quotes inside f-strings needs Python 3.12+")
    def test_nested_fstring(self):
        ns = run('x = 3; s = f"{x:{x}d}|{f"{x}"}|{"}"}"')
        self.assertEqual(ns["s"], "  3|3|}")

    def test_lambda_dict(self):
        ns = run("f = lambda k: {k: 1}; r = f('a')")
        self.assertEqual(ns["r"], {"a": 1})

    def test_decorator_and_async(self):
        ns = run(textwrap.dedent("""
            import asyncio, functools
            def twice(fn) { @functools.wraps(fn)
              async def w(*a) { return 2 * await fn(*a) }; return w }
            @twice
            async def one() { return 1 }
            r = asyncio.run(one())
        """))
        self.assertEqual(ns["r"], 2)

    def test_comments(self):
        self.check("# top\nx = 1  # trailing\nif x { # head\n y = 2 }", """
            # top
            x = 1  # trailing
            if x:  # head
                y = 2
        """)

    def test_soft_keywords_as_names(self):
        ns = run("match = {1: 2}; case = match[1]; type = case")
        self.assertEqual(ns["type"], 2)

    def test_errors(self):
        for src in ["if x { a", "x = (1", "}", "x = (1; 2)", "a = !b", "s = 'abc"]:
            with self.assertRaises(PyjSyntaxError, msg=src):
                transpile(src)

    def test_error_messages(self):
        cases = {
            "if x { a": "block '{' was never closed",
            "x = (1": "'(' was never closed",
            "}": "unmatched '}'",
            "x = (1]": "closing ']' does not match opening '('",
            "x = (1; 2)": "';' is not allowed inside brackets",
            "a = !b": "'!' is not supported; use 'not'",
            "s = 'abc": "unterminated string literal",
            "s = 'abc\nx'": "unterminated string literal (newline in a single-quoted string)",
            "x = $": "invalid character '$'",
        }
        for src, msg in cases.items():
            with self.assertRaises(PyjSyntaxError, msg=src) as cm:
                transpile(src)
            self.assertEqual(cm.exception.msg, msg)

    def test_cli_and_import_hook(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "helper.pyj"), "w", encoding="utf-8") as f:
                f.write("def hi(n) { return f'hi {n}' }")
            with open(os.path.join(d, "main.pyj"), "w", encoding="utf-8") as f:
                f.write("import sys, helper; print(helper.hi(sys.argv[1]))")
            out = subprocess.run([sys.executable, PYJ, "run", os.path.join(d, "main.pyj"), "bob"],
                                 capture_output=True, text=True)
            self.assertEqual(out.stdout, "hi bob\n", out.stderr)
            self.assertTrue(os.path.isdir(os.path.join(d, "__pycache__")))


needs_cols = unittest.skipIf(sys.version_info < (3, 11), "traceback columns need Python 3.11+")


def pyj_cli(*args, input=None, env=None):
    return subprocess.run([sys.executable, PYJ, *args], input=input, capture_output=True,
                          text=True, encoding="utf-8", env=env)


class TestCommandLine(unittest.TestCase):
    def test_c(self):
        out = pyj_cli("-c", "import sys; if 1 { print(sys.argv) }", "a", "b")
        self.assertEqual(out.stdout, "['-c', 'a', 'b']\n", out.stderr)

    def test_stdin(self):
        code = "for i in range(3) { print(i) }"
        self.assertEqual(pyj_cli(input=code).stdout, "0\n1\n2\n")
        out = pyj_cli("-", "x", input="import sys; print(sys.argv)")
        self.assertEqual(out.stdout, "['-', 'x']\n", out.stderr)

    def test_c_traceback_shows_source(self):
        out = pyj_cli("-c", "x = 1\nif x { y = x / 0 }")
        self.assertEqual(out.returncode, 1)
        self.assertIn('File "<string>", line 2', out.stderr)
        self.assertIn("if x { y = x / 0 }", out.stderr)

    def test_build_c_and_stdin(self):
        self.assertEqual(pyj_cli("build", "-c", "if a { b() }").stdout, "if a:\n    b()\n")
        self.assertEqual(pyj_cli("build", "-", input="while 0 {}").stdout, "while 0:\n    pass\n")
        self.assertEqual(pyj_cli("build", "-c", "x", "f.pyj").returncode, 2)

    def test_version(self):
        self.assertEqual(pyj_cli("--version").stdout.strip(), f"pyj {_pyj.__version__}")


@unittest.skipIf(sys.prefix != sys.base_prefix or not __import__("site").ENABLE_USER_SITE,
                 "needs a Python outside a venv with the user site-packages enabled")
class TestInstall(unittest.TestCase):
    """Installs into a temporary PYTHONUSERBASE, leaving the real user directory alone."""

    def test_install_run_uninstall(self):
        import shutil
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, PYTHONUSERBASE=os.path.join(d, "userbase"), PYTHONUTF8="1")
            dl, work = os.path.join(d, "download"), os.path.join(d, "work")
            os.makedirs(dl)
            os.makedirs(work)
            shutil.copy(PYJ, dl)
            out = subprocess.run([sys.executable, os.path.join(dl, "pyj.py"), "install"],
                                 capture_output=True, text=True, env=env)
            self.assertEqual(out.returncode, 0, out.stderr)
            shutil.rmtree(dl)       # the downloaded file is not needed after installing

            with open(os.path.join(work, "app.pyj"), "w", encoding="utf-8") as f:
                f.write("import sys, m; if 1 { print(m.hi(), sys.argv[1]) }")
            with open(os.path.join(work, "m.pyj"), "w", encoding="utf-8") as f:
                f.write("def hi() { return 'ok' }")
            run = subprocess.run([sys.executable, "app.pyj", "arg"], cwd=work,
                                 capture_output=True, text=True, env=env)
            self.assertEqual(run.stdout, "ok arg\n", run.stderr)

            scripts = subprocess.run(
                [sys.executable, "-c", "import sysconfig; print(sysconfig.get_path('scripts', "
                 "sysconfig.get_preferred_scheme('user')))"],
                capture_output=True, text=True, env=env).stdout.strip()
            launcher = os.path.join(scripts, "pyj.cmd" if os.name == "nt" else "pyj")
            cmd = ["cmd", "/c", launcher] if os.name == "nt" else [launcher]
            out = subprocess.run(cmd + ["-c", "if 1 { print('launcher') }"],
                                 capture_output=True, text=True, env=env)
            self.assertEqual(out.stdout.strip(), "launcher", out.stderr)

            out = subprocess.run(cmd + ["uninstall"], capture_output=True, text=True, env=env)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertFalse(os.path.exists(launcher))
            run = subprocess.run([sys.executable, "-c", "import pyj"], cwd=work,
                                 capture_output=True, text=True, env=env)
            self.assertNotEqual(run.returncode, 0)


class TestSourceMap(unittest.TestCase):
    def frame_of(self, src):
        try:
            exec(compile_pyj(src, "<map-test>"), {})
        except Exception as e:
            return traceback.extract_tb(e.__traceback__)[-1]
        self.fail("no exception was raised")

    @needs_cols
    def test_runtime_line_and_col(self):
        src = "def f(a, b) { x = 1; return a /\n    b }\nf(1, 0)"
        fr = self.frame_of(src)
        self.assertEqual((fr.lineno, fr.end_lineno), (1, 2))
        self.assertEqual((fr.colno, fr.end_colno), (28, 5))
        self.assertEqual(fr.line, "def f(a, b) { x = 1; return a /")

    @needs_cols
    def test_same_line_statements(self):
        fr = self.frame_of("a = 1; b = 2; c = undefined_name; d = 4")
        self.assertEqual((fr.lineno, fr.colno, fr.end_colno), (1, 18, 32))

    @needs_cols
    def test_unicode_columns(self):
        fr = self.frame_of("名字 = '中文'; if 名字 { 名字.不存在() }")
        self.assertEqual(fr.lineno, 1)
        # like CPython, colno is a UTF-8 byte offset
        self.assertEqual(fr.line.encode()[fr.colno:fr.end_colno].decode(), "名字.不存在")

    @needs_cols
    def test_else_if_and_empty_block(self):
        fr = self.frame_of("if False {}\nelse if 1 / 0 {}")
        self.assertEqual((fr.lineno, fr.line[fr.colno:fr.end_colno]), (2, "1 / 0"))

    def test_lineno_only(self):
        fr = self.frame_of("x = 1\nif x {\n  y = 2; z = 1 / 0 }")
        self.assertEqual(fr.lineno, 3)

    def test_python_syntax_error_mapped(self):
        with self.assertRaises(SyntaxError) as cm:
            compile_pyj("ok = 1\nif ok { x = = 2 }", "<map-test>")
        self.assertEqual((cm.exception.lineno, cm.exception.offset), (2, 13))


if __name__ == "__main__":
    unittest.main()
