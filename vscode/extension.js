// pyj for VS Code: language support for .pyj files, plus checking / installing pyj itself
// and running or converting the current file.
// Python is always started directly with an argument list (never through a shell), so paths with
// spaces and the differences between PowerShell, cmd and bash do not matter.
"use strict";
const vscode = require("vscode");
const cp = require("child_process");
const path = require("path");

const PYJ_RAW = "https://raw.githubusercontent.com/yyszh01/pyj/main/pyj.py";
const GUIDE = "https://github.com/yyszh01/pyj/tree/main/vscode#installing-pyj";
const MIN_PY = [3, 8];

let output;           // OutputChannel "pyj"
let runTerminal;      // terminal reused by "Run this file"
let checkedThisSession = false;

// ------------------------------------------------------------------ helpers (exported for tests)

/** The Python to use: pyj.pythonPath, else the Python extension's interpreter, else python3 / python. */
async function findPython(doc) {
  const cfg = vscode.workspace.getConfiguration("pyj", doc ? doc.uri : undefined).get("pythonPath");
  if (cfg && cfg.trim()) return cfg.trim();
  if (vscode.extensions.getExtension("ms-python.python")) {
    try {
      const folder = doc ? vscode.workspace.getWorkspaceFolder(doc.uri) : undefined;
      const p = await vscode.commands.executeCommand("python.interpreterPath",
        folder ? { workspaceFolder: folder.uri.fsPath } : undefined);
      if (typeof p === "string" && p.trim()) return p.trim();
    } catch (_) { /* the Python extension is not ready or has no interpreter selected */ }
  }
  return process.platform === "win32" ? "python" : "python3";
}

/** Run python with args (no shell); resolves {code, stdout, stderr, error}. */
function runPython(python, args, opts = {}) {
  return new Promise((resolve) => {
    cp.execFile(python, args, { timeout: opts.timeout || 20000, cwd: opts.cwd, windowsHide: true },
      (error, stdout, stderr) => resolve({
        code: error ? (typeof error.code === "number" ? error.code : -1) : 0,
        stdout: String(stdout || ""), stderr: String(stderr || ""), error,
      }));
  });
}

/**
 * Is pyj importable by this Python?
 * -> {python, found:false}                       Python itself could not be started
 *    {python, found:true, pyVersion, tooOld}     Python older than 3.8
 *    {python, found:true, pyVersion, pyj}        pyj = version string, or null when not installed
 */
async function checkInstalled(python) {
  const code = "import sys; print('%d.%d.%d' % sys.version_info[:3])\n" +
               "try:\n import pyj; print(pyj.__version__)\nexcept Exception:\n print('')";
  const r = await runPython(python, ["-c", code]);
  if (r.error && (r.error.code === "ENOENT" || r.error.code === "EACCES")) return { python, found: false };
  const lines = r.stdout.split(/\r?\n/);
  const pyVersion = lines[0] && /^\d+\.\d+/.test(lines[0]) ? lines[0].trim() : null;
  if (!pyVersion) return { python, found: false, detail: (r.stderr || r.stdout).trim() };
  const [maj, min] = pyVersion.split(".").map(Number);
  if (maj < MIN_PY[0] || (maj === MIN_PY[0] && min < MIN_PY[1])) return { python, found: true, pyVersion, tooOld: true };
  return { python, found: true, pyVersion, pyj: (lines[1] || "").trim() || null };
}

/** Arguments for the two ways of installing pyj with a given Python. */
function installArgs(method) {
  if (method === "pip") return ["-m", "pip", "install", "--upgrade", "pybrace"];
  // the pip-free installer from the README, in Python so it works the same on every OS:
  // download pyj.py into a temporary directory, run `pyj.py install`, delete it
  const script = [
    "import os, subprocess, sys, tempfile, urllib.request",
    "d = tempfile.mkdtemp(); p = os.path.join(d, 'pyj.py')",
    `print('Downloading ${PYJ_RAW}'); urllib.request.urlretrieve('${PYJ_RAW}', p)`,
    "r = subprocess.call([sys.executable, p, 'install'])",
    "os.remove(p); os.rmdir(d); sys.exit(r)",
  ].join("\n");
  return ["-c", script];
}

// ------------------------------------------------------------------ UI

async function reportAndOfferInstall(state, { quietIfOk = false } = {}) {
  await vscode.commands.executeCommand("setContext", "pyj.installed", !!(state.found && state.pyj));
  if (!state.found) {
    const pick = await vscode.window.showErrorMessage(
      `pyj: could not start Python ("${state.python}"). Install Python 3.8+, or set "pyj.pythonPath".`,
      "Open Settings", "Installation Guide");
    if (pick === "Open Settings") vscode.commands.executeCommand("workbench.action.openSettings", "pyj.pythonPath");
    if (pick === "Installation Guide") vscode.env.openExternal(vscode.Uri.parse(GUIDE));
    return;
  }
  if (state.tooOld) {
    vscode.window.showErrorMessage(`pyj needs Python 3.8 or newer; "${state.python}" is ${state.pyVersion}.`);
    return;
  }
  if (state.pyj) {
    if (!quietIfOk) vscode.window.showInformationMessage(`pyj ${state.pyj} is installed for Python ${state.pyVersion} (${state.python}).`);
    return;
  }
  const pick = await vscode.window.showWarningMessage(
    `pyj is not installed for Python ${state.pyVersion} (${state.python}). You can edit .pyj files, but not run them.`,
    "Install pyj…", "Installation Guide", "Don't Ask Again");
  if (pick === "Install pyj…") vscode.commands.executeCommand("pyj.install");
  if (pick === "Installation Guide") vscode.env.openExternal(vscode.Uri.parse(GUIDE));
  if (pick === "Don't Ask Again") vscode.workspace.getConfiguration("pyj").update("checkOnOpen", false, vscode.ConfigurationTarget.Global);
}

async function cmdCheck() {
  const python = await findPython(activeDoc());
  reportAndOfferInstall(await checkInstalled(python));
}

async function cmdInstall() {
  const python = await findPython(activeDoc());
  const state = await checkInstalled(python);
  if (!state.found || state.tooOld) return reportAndOfferInstall(state);
  const items = [
    { label: "$(package) pip install pybrace", method: "pip",
      detail: "For a virtual environment, Windows and macOS. Fails on Debian/Ubuntu system Python (\"externally-managed-environment\")." },
    { label: "$(cloud-download) pyj installer (no pip)", method: "installer",
      detail: "For Debian, Ubuntu and other systems where pip is restricted. Installs into your user directory; no sudo." },
  ];
  const pick = await vscode.window.showQuickPick(items, {
    title: `Install pyj for Python ${state.pyVersion} (${python})`,
    placeHolder: state.pyj ? `pyj ${state.pyj} is installed — pick a method to upgrade` : "How do you want to install pyj?",
  });
  if (!pick) return;
  const args = installArgs(pick.method);
  output.clear();
  output.show(true);
  output.appendLine(`$ ${python} ${pick.method === "pip" ? args.join(" ") : "-c <download pyj.py; pyj.py install>"}`);
  const ok = await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: "Installing pyj…" },
    () => new Promise((resolve) => {
      const child = cp.spawn(python, args, { windowsHide: true });
      child.stdout.on("data", (d) => output.append(String(d)));
      child.stderr.on("data", (d) => output.append(String(d)));
      child.on("error", (e) => { output.appendLine(String(e)); resolve(false); });
      child.on("close", (code) => { output.appendLine(`\n(exit status ${code})`); resolve(code === 0); });
    }));
  const after = await checkInstalled(python);
  if (ok && after.pyj) {
    await vscode.commands.executeCommand("setContext", "pyj.installed", true);
    vscode.window.showInformationMessage(`pyj ${after.pyj} installed for Python ${after.pyVersion}. Try "pyj: Run This File".`);
  } else {
    const hint = pick.method === "pip" && /externally-managed-environment/.test(output.lastText || "")
      ? " This Python's pip is restricted (PEP 668): try the pyj installer instead." : "";
    const again = await vscode.window.showErrorMessage(`Installing pyj failed; see the "pyj" output.${hint}`, "Try Again", "Installation Guide");
    if (again === "Try Again") cmdInstall();
    if (again === "Installation Guide") vscode.env.openExternal(vscode.Uri.parse(GUIDE));
  }
}

function activeDoc() {
  const e = vscode.window.activeTextEditor;
  return e ? e.document : undefined;
}

async function pyjDocOrWarn() {
  const doc = activeDoc();
  if (!doc || doc.languageId !== "pyj") {
    vscode.window.showWarningMessage("Open a .pyj file first.");
    return undefined;
  }
  if (doc.isUntitled) {
    const saved = await vscode.window.showWarningMessage("Save the file first (as .pyj).", "Save");
    if (saved !== "Save" || !(await doc.save()) || doc.isUntitled) return undefined;
  } else if (doc.isDirty) {
    await doc.save();
  }
  return doc;
}

async function ensureInstalled(python) {
  const state = await checkInstalled(python);
  if (state.found && !state.tooOld && state.pyj) return true;
  reportAndOfferInstall(state);
  return false;
}

async function cmdRun() {
  const doc = await pyjDocOrWarn();
  if (!doc) return;
  const python = await findPython(doc);
  if (!(await ensureInstalled(python))) return;
  // a terminal running Python directly (no shell): input() works, nothing to quote
  if (runTerminal && runTerminal.exitStatus === undefined) runTerminal.dispose();
  runTerminal = vscode.window.createTerminal({
    name: `pyj: ${path.basename(doc.fileName)}`,
    shellPath: python,
    shellArgs: [doc.fileName],
    cwd: path.dirname(doc.fileName),
  });
  runTerminal.show();
}

async function cmdBuild() {
  const doc = await pyjDocOrWarn();
  if (!doc) return;
  const python = await findPython(doc);
  if (!(await ensureInstalled(python))) return;
  const r = await runPython(python, ["-m", "pyj", "build", doc.fileName], { cwd: path.dirname(doc.fileName) });
  const target = doc.fileName.replace(/\.pyj$/i, ".py");
  if (r.code !== 0) {
    output.clear();
    output.append(r.stderr || r.stdout || String(r.error));
    output.show(true);
    vscode.window.showErrorMessage("pyj build failed; see the \"pyj\" output.");
    return;
  }
  const opened = await vscode.workspace.openTextDocument(target);
  vscode.window.showTextDocument(opened, { viewColumn: vscode.ViewColumn.Beside, preview: true });
}

const SAMPLE = `# hello.pyj — Python with braces: indentation doesn't matter here
def fib(n) { a, b = 0, 1; for _ in range(n) { a, b = b, a + b }; return a }

for i in range(10) {
print(i, fib(i))   # not indented, still inside the loop
}

if __name__ == "__main__" { print("done") }
`;

async function cmdNewFile() {
  const doc = await vscode.workspace.openTextDocument({ language: "pyj", content: SAMPLE });
  vscode.window.showTextDocument(doc);
}

// ------------------------------------------------------------------ activation

function activate(context) {
  output = vscode.window.createOutputChannel("pyj");
  // remember the output so a failed pip install can be recognised (PEP 668)
  const append = output.append.bind(output);
  output.lastText = "";
  output.append = (s) => { output.lastText = (output.lastText + s).slice(-20000); append(s); };
  const clear = output.clear.bind(output);
  output.clear = () => { output.lastText = ""; clear(); };

  context.subscriptions.push(
    output,
    vscode.commands.registerCommand("pyj.run", cmdRun),
    vscode.commands.registerCommand("pyj.build", cmdBuild),
    vscode.commands.registerCommand("pyj.checkInstall", cmdCheck),
    vscode.commands.registerCommand("pyj.install", cmdInstall),
    vscode.commands.registerCommand("pyj.newFile", cmdNewFile),
    vscode.window.onDidCloseTerminal((t) => { if (t === runTerminal) runTerminal = undefined; }),
  );

  // check once per session when a .pyj file is opened
  const maybeCheck = async (doc) => {
    if (checkedThisSession || !doc || doc.languageId !== "pyj") return;
    if (!vscode.workspace.getConfiguration("pyj").get("checkOnOpen", true)) return;
    checkedThisSession = true;
    reportAndOfferInstall(await checkInstalled(await findPython(doc)), { quietIfOk: true });
  };
  context.subscriptions.push(vscode.workspace.onDidOpenTextDocument(maybeCheck));
  maybeCheck(activeDoc());
}

function deactivate() {}

module.exports = { activate, deactivate, findPython, checkInstalled, installArgs, runPython };
