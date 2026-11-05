# Prometheus Launcher

Windows desktop launcher for a local [Prometheus](https://github.com/prometheus-lua/Prometheus) checkout. Pick a Lua file, an output folder, a preset, and Lua 5.1 or LuaU. The launcher runs Prometheus and prepends a short credit line to the output.

This repository is a wrapper. It does not include Prometheus.

Based on Prometheus by Elias Oelschner, https://github.com/prometheus-lua/Prometheus

## What you need

You need a local Prometheus source checkout. This repository does not include it.

`cli.lua` by itself is not enough. The full GitHub tree is not required either.

Upstream `cli.lua` (master) only sets `package.path` from its own directory and runs `require("src.cli")`. `src/cli.lua` then sets `package.path` from the `src/` directory and runs `require("prometheus")`, which is `src/prometheus.lua`. That module loads `src/presets.lua` and the pipeline. `src/prometheus/pipeline.lua` loads the parser, steps, name generators, and unparser. `src/prometheus/steps.lua` loads every step at startup, including Cff and Vmify, which load `src/prometheus/cff/` and `src/prometheus/vm/`. A successful run therefore needs the root `cli.lua` and the whole `src/` tree, not one file.

Clone upstream and leave `cli.lua` and `src/` intact:

```bat
git clone https://github.com/prometheus-lua/Prometheus.git
```

The launcher does not search the disk for Prometheus. It accepts a checkout only when the selected root `cli.lua` has these three files beside it:

- `src/cli.lua`
- `src/prometheus.lua`
- `src/prometheus/pipeline.lua`

That is a spot check, not the file list Prometheus loads. A folder with only those three files passes the launcher and then fails inside Lua. Keep every `.lua` file under `src/`, including `src/presets.lua`, `src/config.lua`, `src/colors.lua`, `src/logger.lua`, and `src/highlightlua.lua`. Select the root `cli.lua`. Do not select `src/cli.lua`.

You do not need these to obfuscate a file:

- `doc/`, `tests/`, `web/`, `benchmarks/`, `assets/`, `scripts/`, `.github/`
- Docker files, `install.sh`, or the packaged `prometheus-lua` binary
- Node or pnpm files (`package.json`, lockfiles)
- `benchmark.lua`, `prometheus-main.lua`

Do not copy Prometheus into this repository. Point the launcher at your checkout.

You also need a Lua interpreter. Upstream source usage asks for LuaJIT or Lua 5.1+. This launcher looks for a Windows Lua first, in this order: `lua55`, `lua`, `luajit`, `lua5.1`, `lua5.4`, `lua5.3`. Cygwin is optional and is used only when no Windows Lua is found.

## Install the launcher

The Release executable does not need Python. Download `PrometheusLauncher.exe` from this repository's GitHub Releases page once a release has been published. Until then, run the script or build the executable locally (below).

There is no installer. The program is one windowed executable. It does not install a service, register a file association, or write to the registry.

## First run

1. Start `PrometheusLauncher.exe`, or run `py -3 prometheus_launcher.py`.
2. When asked, select `cli.lua` at the root of your Prometheus checkout. Do not select `src/cli.lua`.
3. Choose an input file and an existing output folder. The output name is `<input-name>.obfuscate.lua` inside that folder.
4. Choose a preset (`Minify`, `Weak`, `Medium`, `Strong`) and a version (`Lua51` or `LuaU`).
5. Click Run Prometheus.

Leave **Lua** and **Cygwin bash** blank unless automatic detection picked the wrong program. Use Browse on those rows to override them. Prometheus `cli.lua` is never discovered; you must select it.

Paths are remembered in `%APPDATA%\PrometheusLauncher\config.json`.

## Path overrides

The boxes are filled from the environment variable when it is set, otherwise from the config file. Run uses what is in the box. A blank Lua or Cygwin bash box means discover. A blank Prometheus path does not; there is no search for `cli.lua`.

`--check` is for the Python entrypoint. It opens no window. It uses the environment variable, then the config file, then discovery for Lua and Cygwin bash only. The windowed executable has no console, so do not use it for this check.

| Purpose | Environment variable | Config key |
| --- | --- | --- |
| Prometheus `cli.lua` | `PROMETHEUS_LAUNCHER_CLI` | `prometheus_cli` |
| Lua interpreter | `PROMETHEUS_LAUNCHER_LUA` | `lua_bin` |
| Cygwin `bash.exe` | `PROMETHEUS_LAUNCHER_BASH` | `cygwin_bash` |

Names and empty values are in `.env.example`.

`PROMETHEUS_LAUNCHER_LUA` may be a path to `lua.exe` / `lua55.exe`, or a command name such as `lua55`. `PROMETHEUS_LAUNCHER_BASH` must be Cygwin's `bash.exe`. The same folder must contain `cygwin1.dll`. Git Bash is rejected.

Cygwin bash is discovered from `CYGWIN_HOME`, `CYGWIN_ROOT`, the Cygwin setup registry key, well-known install folders, and `PATH`. It is not pinned to one drive letter.

Diagnosis without opening the window:

```bat
py -3 prometheus_launcher.py --check
```

`ok: yes` means a Lua interpreter and a usable checkout were both found.

## Run from source

Python 3.10 or newer, with tkinter (included in the official Windows installer). No third-party packages are required to run the script.

```bat
py -3 prometheus_launcher.py
```

`prometheus_launcher.py` is the source entrypoint. The executable does not replace it.

## Build the executable

From this directory, with the same Python you use above:

```bat
py -3 -m pip install pyinstaller
py -3 -m PyInstaller --noconfirm PrometheusLauncher.spec
```

The spec builds a windowed one-file executable named `PrometheusLauncher.exe` from `prometheus_launcher.py`. Output:

```text
dist\PrometheusLauncher.exe
```

`build/` and `dist/` are gitignored. Do not commit them.

## Behavior

- Presets offered: Minify, Weak, Medium, Strong. Those names are in upstream `src/presets.lua`. Upstream also defines Cff and Vmify; this launcher does not offer them.
- Version passes `--Lua51` or `--LuaU`.
- Logs are forced to `--nocolors` so the window can show them.
- On success, the output file starts with a UTC credit comment. Prometheus's own license does not require that comment on generated files; it is a launcher convenience.
- A short sound and a three-second popup report success or failure.

## License note

Prometheus is under the Prometheus License: https://github.com/prometheus-lua/Prometheus/blob/master/LICENSE

This launcher wraps Prometheus and does not vendor it. The attribution line above is required by that license. Generated obfuscated files do not need a Prometheus copyright notice.
