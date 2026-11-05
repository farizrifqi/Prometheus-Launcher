# Development Guide

## Requirements

| Tool | Version | Evidence |
| --- | --- | --- |
| Python | 3.10 or newer, with tkinter | `str \| None` in `prometheus_launcher.py`; README |
| Lua | LuaJIT or Lua 5.1+ for source Prometheus | upstream README; launcher search order in `WINDOWS_LUA_NAMES` |
| Prometheus checkout | root `cli.lua` plus the whole `src/` tree | upstream `cli.lua`, `src/cli.lua`, `src/prometheus.lua` |
| PyInstaller | only to build the exe; not pinned | `requirements.txt`, `PrometheusLauncher.spec` |
| Cygwin | optional fallback | `discover_cygwin_bash` |

## Common commands

| Task | Command | Evidence |
| --- | --- | --- |
| Run the window | `py -3 prometheus_launcher.py` | `prometheus_launcher.py` docstring, README |
| Check paths | `py -3 prometheus_launcher.py --check` | `main`, README |
| Compile check | `py -3 -m py_compile prometheus_launcher.py` | no test suite |
| Install the build tool | `py -3 -m pip install pyinstaller` | `requirements.txt` |
| Build the exe | `py -3 -m PyInstaller --noconfirm PrometheusLauncher.spec` | spec, README |

`--check` prints `ok: yes` only when a Lua interpreter and a checkout that passes the spot check were both found. The windowed exe has no console. Do not use it for `--check`.

## Configuration

| File / variable | Purpose | Required? |
| --- | --- | --- |
| `PROMETHEUS_LAUNCHER_CLI` | Path to checkout-root `cli.lua` | Required to run; not discovered |
| `PROMETHEUS_LAUNCHER_LUA` | Lua path or command name | No. Empty means discover |
| `PROMETHEUS_LAUNCHER_BASH` | Cygwin `bash.exe` | No. Used only when Windows Lua is missing |
| `.env.example` | Those three names, empty values | Template only |
| `%APPDATA%\PrometheusLauncher\config.json` | Remembered paths | Created on save |

## Validation checklist

- [x] `py -3 -m py_compile prometheus_launcher.py` exited 0
- [x] Checkout helpers reject `cli.lua` alone, reject `src/cli.lua`, and accept the three spot-check files
- [x] `py -3 -m PyInstaller --noconfirm PrometheusLauncher.spec` completed and rebuilt `dist/PrometheusLauncher.exe`
- [ ] GUI was not opened in this pass
- [ ] A real Prometheus obfuscation was not run in this pass
