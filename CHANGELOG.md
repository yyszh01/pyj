# Changelog

## 0.1.5 — 2026-11

- **Python 3.8 and 3.9 are supported** (they are still the system Python on RHEL 9 and its rebuilds, Debian 11 and Ubuntu 20.04). Tested in CI on Linux and Windows. On 3.8 and 3.9, `python app.pyj` does not pass interpreter flags on, and tracebacks show lines but not columns (columns need 3.11, as before).
- `pyj -c` and code from stdin: tracebacks show the offending source line again with the system Python of Ubuntu and Debian, whose apport crash reporter replaces `sys.excepthook`.
- READMEs: a new opening (what pyj is for and who it is for), and a Feedback section. Bug reports now use issue forms, and questions and ideas go to [Discussions](https://github.com/yyszh01/pyj/discussions).
- The `match` / `case` example moved to `examples/match.pyj` (needs 3.10+), so `examples/demo.pyj` runs on every supported version.

## 0.1.4 and earlier — 2026-10

First releases: blocks in `{ }`, `.pyj` files run and import transparently, error positions mapped back to the `.pyj` source, `pyj -c` / stdin, `pyj build`, and a pip-free installer. See the [git history](https://github.com/yyszh01/pyj/commits/main) for details.
