// Grammar tests: tokenize pyj with the same engine VS Code uses (vscode-textmate + oniguruma)
// and VS Code's Python grammar (test/fixtures/MagicPython.tmLanguage.json, from microsoft/vscode 1.95.0, MIT).
// Run: npm test
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const vsctm = require("vscode-textmate");
const oniguruma = require("vscode-oniguruma");

const root = path.join(__dirname, "..");
const grammars = {
  "source.pyj": path.join(root, "syntaxes", "pyj.tmLanguage.json"),
  "source.python": path.join(__dirname, "fixtures", "MagicPython.tmLanguage.json"),
};

let registry;
async function grammar() {
  if (!registry) {
    const wasm = fs.readFileSync(require.resolve("vscode-oniguruma/release/onig.wasm")).buffer;
    await oniguruma.loadWASM(wasm);
    registry = new vsctm.Registry({
      onigLib: Promise.resolve({
        createOnigScanner: (p) => new oniguruma.OnigScanner(p),
        createOnigString: (s) => new oniguruma.OnigString(s),
      }),
      loadGrammar: async (scope) =>
        grammars[scope] ? vsctm.parseRawGrammar(fs.readFileSync(grammars[scope], "utf8"), grammars[scope]) : null,
    });
  }
  return registry.loadGrammar("source.pyj");
}

// [{line, text, scopes}] for every token
async function tokenize(src) {
  const g = await grammar();
  let stack = vsctm.INITIAL;
  const out = [];
  src.split("\n").forEach((line, i) => {
    const r = g.tokenizeLine(line, stack);
    for (const t of r.tokens) out.push({ line: i + 1, text: line.slice(t.startIndex, t.endIndex), scopes: t.scopes });
    stack = r.ruleStack;
  });
  return out;
}

// scopes of the n-th token (0-based) whose trimmed text is `text`, optionally on a given line
function scopesOf(tokens, text, { line, nth = 0 } = {}) {
  const hits = tokens.filter((t) => t.text.trim() === text && (line === undefined || t.line === line));
  assert.ok(hits[nth], `no token ${JSON.stringify(text)}${line ? " on line " + line : ""}`);
  return hits[nth].scopes.join(" ");
}
const has = (scopes, s) => assert.ok(scopes.includes(s), `expected ${s} in: ${scopes}`);
const hasNot = (scopes, s) => assert.ok(!scopes.includes(s), `did not expect ${s} in: ${scopes}`);

test("statements inside a multi-line block keep Python highlighting", async () => {
  const t = await tokenize([
    "def fib(n) {",
    "    import math",
    "    a, b = 0, 1",
    "    for _ in range(n) {",
    "        a, b = b, a + b",
    "    }",
    "    return a",
    "}",
  ].join("\n"));
  has(scopesOf(t, "def"), "storage.type.function.python");
  has(scopesOf(t, "fib"), "entity.name.function.python");
  has(scopesOf(t, "import"), "keyword.control.import.python");
  has(scopesOf(t, "for"), "keyword.control.flow.python");
  has(scopesOf(t, "return"), "keyword.control.flow.python");
  has(scopesOf(t, "return"), "meta.block.pyj");
  has(scopesOf(t, "{", { line: 1 }), "punctuation.section.block.begin.pyj");
  has(scopesOf(t, "}", { line: 8 }), "punctuation.section.block.end.pyj");
  hasNot(scopesOf(t, "return"), "meta.structure.dict");
});

test("one-line def and nested blocks", async () => {
  const t = await tokenize('def fib(n) { a, b = 0, 1; for _ in range(n) { a, b = b, a + b }; return a }');
  has(scopesOf(t, "fib"), "entity.name.function.python");
  has(scopesOf(t, "for"), "keyword.control.flow.python");
  has(scopesOf(t, "return"), "keyword.control.flow.python");
  has(scopesOf(t, "range"), "support.function.builtin.python");
});

test("dict and set literals stay dicts", async () => {
  const t = await tokenize([
    'd = {"a": 1, "b": {"c": 2}}',
    "if k in {1, 2} { d = {} }",
    "def f() { return {'x': 1} }",
    "x = [{1: 2}]",
  ].join("\n"));
  has(scopesOf(t, "{", { line: 1 }), "punctuation.definition.dict.begin.python");
  hasNot(scopesOf(t, "{", { line: 1 }), "meta.block.pyj");
  // `in {1, 2}` is a set, the `{` after it is a block
  has(scopesOf(t, "{", { line: 2, nth: 0 }), "punctuation.definition.dict.begin.python");
  has(scopesOf(t, "{", { line: 2, nth: 1 }), "punctuation.section.block.begin.pyj");
  // `return {...}` is a dict inside a block
  has(scopesOf(t, "{", { line: 3, nth: 1 }), "punctuation.definition.dict.begin.python");
  has(scopesOf(t, "'", { line: 3 }), "string.quoted.single.python");
  has(scopesOf(t, "{", { line: 4 }), "punctuation.definition.dict.begin.python");
});

test("if / else if / else, try, class, while, with, match", async () => {
  const t = await tokenize([
    'if n < 0 { print("negative") } else if n == 0 { print("zero") } else { print("positive") }',
    'try { 1 / 0 } except ZeroDivisionError as e { print(e) } finally { print("done") }',
    "class Empty {}",
    "class Point(Base) {",
    "    def __init__(self, x) { self.x = x }",
    "}",
    "while False {}",
    "with open(p) as f { data = f.read() }",
    "match code { case 200 | 201 { return 'ok' } case _ { return 'err' } }",
  ].join("\n"));
  has(scopesOf(t, "else", { line: 1 }), "keyword.control.flow.python");
  has(scopesOf(t, "print", { line: 1 }), "support.function.builtin.python");
  has(scopesOf(t, "except"), "keyword.control.flow.python");
  has(scopesOf(t, "finally"), "keyword.control.flow.python");
  has(scopesOf(t, "Empty"), "entity.name.type.class.python");
  has(scopesOf(t, "Point"), "entity.name.type.class.python");
  has(scopesOf(t, "__init__"), "entity.name.function.python");
  has(scopesOf(t, "{", { line: 3 }), "punctuation.section.block.begin.pyj");
  has(scopesOf(t, "while"), "keyword.control.flow.python");
  has(scopesOf(t, "{", { line: 8 }), "punctuation.section.block.begin.pyj");
  has(scopesOf(t, "return", { line: 9 }), "keyword.control.flow.python");
});

test("comments, strings and f-strings", async () => {
  const t = await tokenize([
    "# a comment { not a block",
    "if x { s = f\"{x} items\"  # trailing }",
    "}",
  ].join("\n"));
  has(scopesOf(t, "#", { line: 1 }), "comment.line.number-sign.python");
  has(scopesOf(t, "x", { line: 2, nth: 1 }), "meta.fstring.python");
  has(scopesOf(t, "}", { line: 3 }), "punctuation.section.block.end.pyj");
});

test("the example files tokenize with every { } balanced", async () => {
  for (const f of ["demo.pyj", "match.pyj"]) {
    const src = fs.readFileSync(path.join(root, "..", "examples", f), "utf8");
    const t = await tokenize(src.replace(/\n+$/, ""));
    const last = t[t.length - 1].scopes.join(" ");
    hasNot(last, "meta.block.pyj");
    hasNot(last, "meta.structure.dict");
    const opens = t.filter((x) => x.scopes.includes("punctuation.section.block.begin.pyj")).length;
    const closes = t.filter((x) => x.scopes.includes("punctuation.section.block.end.pyj")).length;
    assert.strictEqual(opens, closes, `${f}: ${opens} block '{' vs ${closes} '}'`);
    assert.ok(opens > 0, `${f}: no blocks found`);
  }
});
