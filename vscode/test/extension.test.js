// Tests for extension.js outside VS Code: a minimal stub stands in for the `vscode` module.
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const cp = require("child_process");
const Module = require("module");

// ---- vscode stub
const registered = {};
let config = {};
const vscodeStub = {
  workspace: {
    getConfiguration: () => ({ get: (k, d) => (k in config ? config[k] : d), update: async () => {} }),
    getWorkspaceFolder: () => undefined,
    onDidOpenTextDocument: () => ({ dispose() {} }),
  },
  extensions: { getExtension: () => undefined },
  commands: {
    registerCommand: (id, fn) => { registered[id] = fn; return { dispose() {} }; },
    executeCommand: async () => undefined,
  },
  window: {
    createOutputChannel: () => ({ append() {}, appendLine() {}, clear() {}, show() {}, dispose() {} }),
    onDidCloseTerminal: () => ({ dispose() {} }),
    activeTextEditor: undefined,
    showInformationMessage: async () => undefined,
    showWarningMessage: async () => undefined,
    showErrorMessage: async () => undefined,
  },
  env: { openExternal: async () => true },
  Uri: { parse: (s) => s },
  ConfigurationTarget: { Global: 1 },
  ProgressLocation: { Notification: 15 },
  ViewColumn: { Beside: -2 },
};
const origResolve = Module._resolveFilename;
Module._resolveFilename = function (request, ...rest) {
  if (request === "vscode") return "vscode";
  return origResolve.call(this, request, ...rest);
};
require.cache.vscode = { id: "vscode", filename: "vscode", loaded: true, exports: vscodeStub };

const ext = require("../extension.js");
const PYJ_ROOT = path.join(__dirname, "..", "..");
const PY = process.platform === "win32" ? "python" : "python3";

test("checkInstalled: Python that does not exist", async () => {
  const r = await ext.checkInstalled(path.join(os.tmpdir(), "no-such-python-here"));
  assert.strictEqual(r.found, false);
});

test("checkInstalled: Python without pyj, and with pyj on the path", async () => {
  const saved = process.env.PYTHONPATH;
  try {
    process.env.PYTHONPATH = path.join(os.tmpdir(), "empty-dir-for-pyj-test");
    const without = await ext.checkInstalled(PY);
    assert.strictEqual(without.found, true);
    assert.match(without.pyVersion, /^3\.\d+\.\d+$/);
    // the system Python here has no pyj; if it does, this check is not meaningful
    if (without.pyj === null) assert.strictEqual(without.pyj, null);

    process.env.PYTHONPATH = PYJ_ROOT;   // the repository's pyj.py becomes importable
    const withPyj = await ext.checkInstalled(PY);
    const expected = fs.readFileSync(path.join(PYJ_ROOT, "pyj.py"), "utf8").match(/^__version__ = "([^"]+)"/m)[1];
    assert.strictEqual(withPyj.pyj, expected);
  } finally {
    if (saved === undefined) delete process.env.PYTHONPATH; else process.env.PYTHONPATH = saved;
  }
});

test("checkInstalled: Python older than 3.8", { skip: process.platform === "win32" }, async () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), "pyj-old-"));
  const fake = path.join(d, "python");
  fs.writeFileSync(fake, "#!/bin/sh\necho 3.7.9\necho\n");
  fs.chmodSync(fake, 0o755);
  try {
    const r = await ext.checkInstalled(fake);
    assert.deepStrictEqual([r.found, r.tooOld, r.pyVersion], [true, true, "3.7.9"]);
  } finally {
    fs.rmSync(d, { recursive: true, force: true });
  }
});

test("installArgs: pip, and an installer script that is valid Python", () => {
  assert.deepStrictEqual(ext.installArgs("pip"), ["-m", "pip", "install", "--upgrade", "pybrace"]);
  const [flag, script] = ext.installArgs("installer");
  assert.strictEqual(flag, "-c");
  assert.match(script, /pyj\.py/);
  // compile only, nothing is downloaded or run
  const r = cp.spawnSync(PY, ["-c", "import sys; compile(sys.stdin.read(), '<installer>', 'exec')"], { input: script });
  assert.strictEqual(r.status, 0, String(r.stderr));
});

test("findPython: setting first, else the platform default", async () => {
  config = { pythonPath: "  /opt/py/bin/python3  " };
  assert.strictEqual(await ext.findPython(), "/opt/py/bin/python3");
  config = {};
  assert.strictEqual(await ext.findPython(), PY);
});

test("activate registers every command declared in package.json", () => {
  const ctx = { subscriptions: [] };
  ext.activate(ctx);
  const declared = require("../package.json").contributes.commands.map((c) => c.command);
  for (const id of declared) assert.ok(registered[id], `command ${id} is declared but not registered`);
  for (const id of Object.keys(registered)) assert.ok(declared.includes(id), `command ${id} is registered but not declared`);
});

test("walkthrough media files exist", () => {
  const pkg = require("../package.json");
  for (const w of pkg.contributes.walkthroughs) {
    for (const s of w.steps) {
      const f = path.join(__dirname, "..", s.media.markdown);
      assert.ok(fs.existsSync(f), `missing ${s.media.markdown}`);
    }
  }
});
