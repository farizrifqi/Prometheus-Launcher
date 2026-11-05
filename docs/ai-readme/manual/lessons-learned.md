# Lessons Learned

## Pitfalls

| Problem | Cause | Solution |
| --- | --- | --- |
| `cli.lua` alone is rejected | Root `cli.lua` only loads `src/cli.lua` | Keep the whole `src/` tree |
| Spot check passes, Lua then fails | The three checked files are not the full require graph | Do not prune `src/` |
| `src/cli.lua` is rejected | The selected file's parent is treated as the checkout root | Select root `cli.lua` |
| Git Bash is rejected | Acceptance requires `cygwin1.dll` beside `bash.exe` | Use Cygwin bash, or a Windows Lua so bash is unused |
| `--check` on the exe shows nothing | The spec sets `console=False` | Run `py -3 prometheus_launcher.py --check` |

## Decisions

| Decision | Reason | Date / owner |
| --- | --- | --- |
| No custom installer | Distribution choice for the GitHub Release | maintainer, this pass |
| `prometheus_launcher.py` stays the source entrypoint | The exe is only an extra desktop entrypoint | maintainer, this pass |
| Do not commit `build/` or `dist/` | Release asset is attached later, not stored in git | `.gitignore` |
| Do not hardcode one Cygwin root or a personal checkout path | Paths are env, config, or discovery | `prometheus_launcher.py` |
| No version bump | No version file, and the maintainer did not ask | this pass |
