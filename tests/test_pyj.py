import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import traceback  # noqa: E402

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

    @unittest.skipIf(sys.version_info < (3, 12), "f-string 内嵌同种引号需要 Python 3.12+")
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

    def test_cli_and_import_hook(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "helper.pyj"), "w", encoding="utf-8") as f:
                f.write("def hi(n) { return f'hi {n}' }")
            with open(os.path.join(d, "main.pyj"), "w", encoding="utf-8") as f:
                f.write("import sys, helper; print(helper.hi(sys.argv[1]))")
            pyj = os.path.join(os.path.dirname(__file__), "..", "pyj.py")
            out = subprocess.run([sys.executable, pyj, "run", os.path.join(d, "main.pyj"), "bob"],
                                 capture_output=True, text=True)
            self.assertEqual(out.stdout, "hi bob\n", out.stderr)
            self.assertTrue(os.path.isdir(os.path.join(d, "__pycache__")))


needs_cols = unittest.skipIf(sys.version_info < (3, 11), "traceback 列号需要 Python 3.11+")


class TestSourceMap(unittest.TestCase):
    def frame_of(self, src):
        try:
            exec(compile_pyj(src, "<map-test>"), {})
        except Exception as e:
            return traceback.extract_tb(e.__traceback__)[-1]
        self.fail("没有抛出异常")

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
        # colno 和原生 Python 一样是 UTF-8 字节偏移
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
