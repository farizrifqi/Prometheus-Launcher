# AI_README

## Project Overview

Windows GUI wrapper that runs a local Prometheus checkout. It does not include Prometheus. The user selects root `cli.lua`, an input file, an output folder, a preset, and Lua 5.1 or LuaU. The script is the source entrypoint. `dist/PrometheusLauncher.exe` is a windowed extra entrypoint for a later GitHub Release and is gitignored.

## Read next

- usage: `README.md`
- structure: `docs/ai-readme/project-structure.md`
- architecture: `docs/ai-readme/technical-architecture.md`
- commands: `docs/ai-readme/development-guide.md`
- flows: `docs/ai-readme/core-flows.md`
- business context: `docs/ai-readme/manual/business-knowledge.md`
- lessons learned: `docs/ai-readme/manual/lessons-learned.md`
- vulnerability note: `SECURITY.md`

## Development Commands

- Run locally: `py -3 prometheus_launcher.py`
- Check paths: `py -3 prometheus_launcher.py --check`
- Build: `py -3 -m pip install pyinstaller` then `py -3 -m PyInstaller --noconfirm PrometheusLauncher.spec`
- Test: no test suite. `py -3 -m py_compile prometheus_launcher.py` compiles the script.

## Key Directories

- `prometheus_launcher.py` — GUI, discovery, checkout spot check, launch
- `docs/ai-readme/` — agent handoff notes
- `build/`, `dist/` — generated, gitignored

## Boundaries and Constraints

- `cli.lua` alone is not enough. The full upstream GitHub tree is not required. Keep root `cli.lua` and the whole `src/` tree.
- The launcher spot-checks `src/cli.lua`, `src/prometheus.lua`, and `src/prometheus/pipeline.lua`. That gate is not the runtime file list.
- Do not select `src/cli.lua`.
- Prometheus `cli.lua` is not discovered. Lua and Cygwin bash are.
- No personal machine paths in source or docs. Cygwin discovery is env, registry, well-known folders, then `PATH`.
- Do not commit `build/` or `dist/`. Do not add an installer.
- Do not bump a version; this repo does not pin one.
- Required attribution: Based on Prometheus by Elias Oelschner, https://github.com/prometheus-lua/Prometheus
