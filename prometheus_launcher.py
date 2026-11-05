"""Windows GUI for running a local Prometheus checkout.

Run from source:
    py -3 prometheus_launcher.py

Build the windowed executable (do not commit dist/ or build/):
    py -3 -m pip install pyinstaller
    py -3 -m PyInstaller --noconfirm PrometheusLauncher.spec

The executable is an extra desktop entrypoint. This script stays the source entrypoint.
"""

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

try:
    import winsound
except ImportError:
    winsound = None


APP_DIR_NAME = "PrometheusLauncher"
CONFIG_PATH = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_DIR_NAME / "config.json"

ENV_BASH = "PROMETHEUS_LAUNCHER_BASH"
ENV_CLI = "PROMETHEUS_LAUNCHER_CLI"
ENV_LUA = "PROMETHEUS_LAUNCHER_LUA"

PRESETS = ("Minify", "Weak", "Medium", "Strong")
LUA_VERSIONS = ("Lua51", "LuaU")
WINDOWS_LUA_NAMES = ("lua55", "lua", "luajit", "lua5.1", "lua5.4", "lua5.3")
CHECKOUT_FILES = (
    "src/cli.lua",
    "src/prometheus.lua",
    "src/prometheus/pipeline.lua",
)
# Installer defaults used only after the registry, CYGWIN_HOME, and PATH miss.
STANDARD_CYGWIN_ROOTS = (
    r"C:\cygwin64",
    r"C:\cygwin",
    r"D:\cygwin64",
    r"D:\cygwin",
)
PROMETHEUS_CREDIT = (
    "Based on Prometheus by Elias Oelschner, "
    "https://github.com/prometheus-lua/Prometheus"
)


@dataclass(frozen=True)
class Runtime:
    mode: str
    lua: str = ""
    bash: str | None = None
    cli: str = ""
    error: str = ""


def build_credit() -> str:
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S")
    return f"-- File is obfuscated using Prometheus at {now}"


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_config(data: dict) -> None:
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
    except OSError:
        pass


def hidden_kwargs() -> dict:
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "startupinfo": startupinfo,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


def windows_absolute(path: str) -> str:
    value = str(Path(path).resolve())
    prefix = "\\\\?\\"
    if value.startswith(prefix):
        value = value[len(prefix):]
    return value


def to_cygwin_path(path: str) -> str:
    """Turn D:\\work\\a.lua into /cygdrive/d/work/a.lua for a Cygwin Lua."""
    value = windows_absolute(path).replace("\\", "/")
    match = re.fullmatch(r"([A-Za-z]):/(.*)", value)
    if not match:
        raise ValueError(f"Expected an absolute drive path, got: {path}")
    return f"/cygdrive/{match.group(1).lower()}/{match.group(2)}"


def cygwin_to_windows(path: str) -> str | None:
    normalized = path.replace("\\", "/").rstrip("/")
    match = re.fullmatch(r"/cygdrive/([A-Za-z])/(.*)", normalized)
    if not match:
        return None
    win = match.group(1).upper() + ":\\" + match.group(2).replace("/", "\\")
    for candidate in (Path(win), Path(win + ".exe")):
        if candidate.is_file():
            return str(candidate)
    return None


def is_cygwin_bash(path: str) -> bool:
    candidate = Path(path)
    if not candidate.is_file() or candidate.name.lower() != "bash.exe":
        return False
    return (candidate.parent / "cygwin1.dll").is_file()


def cli_root(path: str) -> Path | None:
    if not path or not path.strip():
        return None
    candidate = Path(path.strip())
    if candidate.is_dir():
        candidate = candidate / "cli.lua"
    if not candidate.is_file():
        return None
    return candidate.parent


def cli_checkout_error(path: str) -> str | None:
    root = cli_root(path)
    if root is None:
        return (
            "Choose cli.lua at the root of a Prometheus checkout. "
            "cli.lua alone is not enough; it loads the src directory beside it."
        )
    missing = [rel for rel in CHECKOUT_FILES if not (root / rel).is_file()]
    if missing:
        joined = ", ".join(missing)
        return (
            "That file is not a usable Prometheus checkout. "
            f"Missing beside cli.lua: {joined}. "
            "Clone https://github.com/prometheus-lua/Prometheus and select its cli.lua."
        )
    return None


def resolved_cli(path: str) -> str:
    root = cli_root(path)
    if root is None:
        raise ValueError("Prometheus cli.lua is not set.")
    return str((root / "cli.lua").resolve())


def _registry_cygwin_roots() -> list[str]:
    roots = []
    try:
        import winreg
    except ImportError:
        return roots
    keys = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Cygwin\setup"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Cygwin\setup"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Cygwin\setup"),
    )
    for hive, key_path in keys:
        try:
            with winreg.OpenKey(hive, key_path) as key:
                root, _ = winreg.QueryValueEx(key, "rootdir")
        except OSError:
            continue
        if root:
            roots.append(str(root))
    return roots


def _standard_cygwin_roots() -> list[str]:
    roots = list(STANDARD_CYGWIN_ROOTS)
    for env_name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(env_name)
        if not base:
            continue
        roots.append(str(Path(base) / "cygwin64"))
        roots.append(str(Path(base) / "cygwin"))
    return roots


def discover_cygwin_bash() -> str | None:
    ordered = []
    for env_name in ("CYGWIN_HOME", "CYGWIN_ROOT"):
        value = os.environ.get(env_name)
        if value:
            ordered.append(value)
    ordered.extend(_registry_cygwin_roots())
    ordered.extend(_standard_cygwin_roots())
    seen = set()
    for root in ordered:
        bash = Path(root) / "bin" / "bash.exe"
        key = str(bash).lower()
        if key in seen:
            continue
        seen.add(key)
        if is_cygwin_bash(bash):
            return str(bash)
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if entry and is_cygwin_bash(str(Path(entry) / "bash.exe")):
            return str(Path(entry) / "bash.exe")
    where = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "where.exe"
    if not where.is_file():
        return None
    try:
        result = subprocess.run(
            [str(where), "bash"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            **hidden_kwargs(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in result.stdout.splitlines():
        candidate = line.strip()
        if candidate and is_cygwin_bash(candidate):
            return str(Path(candidate))
    return None


def resolve_bash(explicit: str) -> tuple[str | None, str]:
    chosen = explicit.strip()
    if chosen:
        if is_cygwin_bash(chosen):
            return str(Path(chosen)), ""
        return None, (
            "Cygwin bash was not found at the selected path. "
            "Choose bash.exe from a Cygwin bin folder (cygwin1.dll must sit beside it). "
            "Git Bash cannot run this."
        )
    found = discover_cygwin_bash()
    if found:
        return found, ""
    return None, (
        "Cygwin bash was not found. Install Cygwin, or set "
        f"{ENV_BASH} to its bash.exe. Git Bash does not count."
    )


def discover_windows_lua() -> str | None:
    for name in WINDOWS_LUA_NAMES:
        found = shutil.which(name)
        if found and Path(found).is_file():
            return str(Path(found))
    return None


def discover_lua_in_cygwin(bash: str) -> str | None:
    script = (
        "lua=$(command -v lua55 || command -v lua || command -v luajit "
        "|| command -v lua5.1 || command -v lua5.4 || command -v lua5.3 || true); "
        "printf 'PROM_LUA:%s\\n' \"$lua\""
    )
    try:
        result = subprocess.run(
            [bash, "-lc", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            **hidden_kwargs(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in reversed(result.stdout.splitlines()):
        if line.startswith("PROM_LUA:"):
            found = line[len("PROM_LUA:"):].strip()
            return found or None
    return None


def _windows_lua_from_setting(setting: str) -> str | None:
    if not setting or setting.startswith("/"):
        return None
    candidate = Path(setting)
    if candidate.is_file():
        return str(candidate)
    suffixed = Path(str(candidate) + ".exe")
    if suffixed.is_file():
        return str(suffixed)
    found = shutil.which(setting)
    if found and Path(found).is_file():
        return str(Path(found))
    return None


def resolve_runtime(cli: str, lua_setting: str, bash_setting: str) -> Runtime:
    cli_error = cli_checkout_error(cli)
    cli_value = ""
    if cli_error is None:
        cli_value = resolved_cli(cli)
    lua_setting = lua_setting.strip()
    windows_lua = _windows_lua_from_setting(lua_setting)
    if windows_lua:
        return Runtime("windows", windows_lua, None, cli_value, cli_error or "")
    if lua_setting.startswith("/"):
        bash, bash_error = resolve_bash(bash_setting)
        if not bash:
            return Runtime("missing", "", None, cli_value, bash_error)
        return Runtime("cygwin", lua_setting, bash, cli_value, cli_error or "")
    if lua_setting:
        bash, bash_error = resolve_bash(bash_setting)
        if not bash:
            return Runtime("missing", "", None, cli_value, bash_error)
        return Runtime("cygwin", lua_setting, bash, cli_value, cli_error or "")
    found = discover_windows_lua()
    if found:
        return Runtime("windows", found, None, cli_value, cli_error or "")
    bash, bash_error = resolve_bash(bash_setting)
    if not bash:
        return Runtime(
            "missing",
            "",
            None,
            cli_value,
            "No Windows Lua was found, and " + bash_error,
        )
    cyg_lua = discover_lua_in_cygwin(bash)
    if not cyg_lua:
        return Runtime(
            "missing",
            "",
            bash,
            cli_value,
            "No Lua interpreter was found on PATH or inside Cygwin. "
            f"Install Lua 5.1 or newer, or set {ENV_LUA}.",
        )
    mapped = cygwin_to_windows(cyg_lua)
    if mapped:
        return Runtime("windows", mapped, None, cli_value, cli_error or "")
    return Runtime("cygwin", cyg_lua, bash, cli_value, cli_error or "")


def build_invocation(runtime: Runtime, input_path: str, output_path: str, preset: str, luaver: str):
    cli = windows_absolute(runtime.cli)
    source = windows_absolute(input_path)
    target = windows_absolute(output_path)
    if runtime.mode == "windows":
        args = [
            runtime.lua,
            cli,
            source,
            "--nocolors",
            "--preset",
            preset,
            f"--{luaver}",
            "--out",
            target,
        ]
        return args, target
    if not runtime.bash:
        raise ValueError("Cygwin bash is not set.")
    # bash -lc uses the next argument as $0, then $1 onward. Paths stay out of the script text.
    command = 'exec "$1" "$2" "$3" --nocolors --preset "$4" --"$5" --out "$6"'
    args = [
        runtime.bash,
        "-lc",
        command,
        "prometheus-launcher",
        runtime.lua,
        to_cygwin_path(cli),
        to_cygwin_path(source),
        preset,
        luaver,
        to_cygwin_path(target),
    ]
    return args, target


def prepend_credit(path: str) -> None:
    with open(path, "rb") as handle:
        data = handle.read()
    with open(path, "wb") as handle:
        handle.write(build_credit().encode("utf-8") + b"\n\n" + data)


def run_prometheus(runtime: Runtime, input_path: str, output_path: str, preset: str, luaver: str, log) -> int:
    args, target = build_invocation(runtime, input_path, output_path, preset, luaver)
    log(subprocess.list2cmdline(args))
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        **hidden_kwargs(),
    )
    if process.stdout is not None:
        for line in process.stdout:
            log(line.rstrip())
    code = process.wait()
    if code == 0:
        try:
            prepend_credit(target)
            log("Credit header added.")
        except OSError as exc:
            log(f"Could not add credit header: {exc}")
    return code


def check_lines(cli: str, lua_setting: str, bash_setting: str) -> tuple[list[str], bool]:
    runtime = resolve_runtime(cli, lua_setting, bash_setting)
    lines = [
        "Prometheus Launcher check",
        f"mode: {runtime.mode}",
        f"cli: {runtime.cli or 'missing'}",
        f"lua: {runtime.lua or 'missing'}",
        f"bash: {runtime.bash or 'not used'}",
    ]
    if runtime.error:
        lines.append(f"error: {runtime.error}")
    ok = runtime.mode in {"windows", "cygwin"} and not runtime.error and bool(runtime.lua)
    lines.append("ok: " + ("yes" if ok else "no"))
    return lines, ok


def configured_paths() -> tuple[str, str, str]:
    config = load_config()
    cli = os.environ.get(ENV_CLI) or str(config.get("prometheus_cli", ""))
    lua = os.environ.get(ENV_LUA) or str(config.get("lua_bin", ""))
    bash = os.environ.get(ENV_BASH) or str(config.get("cygwin_bash", ""))
    return cli, lua, bash


def write_check(argv: list[str]) -> int:
    cli, lua, bash = configured_paths()
    lines, ok = check_lines(cli, lua, bash)
    report = "\n".join(lines) + "\n"
    if "--check-file" in argv:
        index = argv.index("--check-file")
        if index + 1 >= len(argv):
            report = "missing path after --check-file\n"
            ok = False
        else:
            Path(argv[index + 1]).write_text(report, encoding="utf-8")
    stream = sys.stdout
    if stream is not None:
        try:
            stream.write(report)
        except OSError:
            pass
    return 0 if ok else 1


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Prometheus Launcher")
        self.resizable(True, True)
        self.minsize(760, 620)
        cached = load_config()
        self.input_file = tk.StringVar(value=cached.get("input_file", ""))
        self.output_folder = tk.StringVar(value=cached.get("output_folder", ""))
        self.output_file = tk.StringVar()
        self.preset = tk.StringVar(value="Weak")
        self.luaver = tk.StringVar(value="Lua51")
        self.cli_path = tk.StringVar(value=os.environ.get(ENV_CLI) or cached.get("prometheus_cli", ""))
        self.lua_bin = tk.StringVar(value=os.environ.get(ENV_LUA) or cached.get("lua_bin", ""))
        self.cygwin_bash = tk.StringVar(value=os.environ.get(ENV_BASH) or cached.get("cygwin_bash", ""))
        self.events = queue.Queue()
        self.input_file.trace_add("write", self.update_output_filename)
        self.output_folder.trace_add("write", self.update_output_filename)
        self._build_ui()
        self.update_output_filename()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self._poll_events)
        self.after(200, self.maybe_prompt_cli)

    def snapshot(self) -> dict:
        return {
            "input_file": self.input_file.get().strip(),
            "output_folder": self.output_folder.get().strip(),
            "prometheus_cli": self.cli_path.get().strip(),
            "lua_bin": self.lua_bin.get().strip(),
            "cygwin_bash": self.cygwin_bash.get().strip(),
        }

    def on_close(self):
        save_config(self.snapshot())
        self.destroy()

    def _build_ui(self):
        root = ttk.Frame(self, padding=14)
        root.grid(sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)

        self._path_row(root, 0, "Input file:", self.input_file, self.choose_input)
        self._path_row(root, 1, "Output folder:", self.output_folder, self.choose_output)

        ttk.Label(root, text="Output file:").grid(row=2, column=0, sticky="w", pady=(0, 8))
        ttk.Entry(root, textvariable=self.output_file, state="readonly").grid(
            row=2, column=1, columnspan=2, sticky="ew", padx=8, pady=(0, 8))

        ttk.Label(root, text="Preset:").grid(row=3, column=0, sticky="w", pady=(0, 8))
        ttk.Combobox(root, textvariable=self.preset, values=PRESETS, state="readonly", width=18).grid(
            row=3, column=1, sticky="w", padx=8, pady=(0, 8))

        ttk.Label(root, text="Version:").grid(row=4, column=0, sticky="w", pady=(0, 8))
        ttk.Combobox(root, textvariable=self.luaver, values=LUA_VERSIONS, state="readonly", width=18).grid(
            row=4, column=1, sticky="w", padx=8, pady=(0, 8))

        self._path_row(root, 5, "Prometheus cli.lua:", self.cli_path, self.choose_cli)
        self._path_row(root, 6, "Lua (optional):", self.lua_bin, self.choose_lua)
        self._path_row(root, 7, "Cygwin bash (optional):", self.cygwin_bash, self.choose_bash)

        ttk.Label(
            root,
            text="Leave Lua and Cygwin blank to detect them. Cygwin is used only when no Windows Lua is found.",
            wraplength=700,
        ).grid(row=8, column=0, columnspan=3, sticky="w", pady=(0, 6))
        ttk.Label(root, text=PROMETHEUS_CREDIT, wraplength=700).grid(
            row=9, column=0, columnspan=3, sticky="w", pady=(0, 8))

        self.run_button = ttk.Button(root, text="Run Prometheus", command=self.run)
        self.run_button.grid(row=10, column=0, columnspan=3, sticky="nw", pady=(0, 10))
        root.rowconfigure(11, weight=1)
        self.log = tk.Text(root, height=12, wrap="word", state="disabled")
        self.log.grid(row=11, column=0, columnspan=3, sticky="nsew")

    def _path_row(self, root, row, label, variable, command):
        ttk.Label(root, text=label).grid(row=row, column=0, sticky="w", pady=(0, 8))
        ttk.Entry(root, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=8, pady=(0, 8))
        ttk.Button(root, text="Browse…", command=command).grid(row=row, column=2, pady=(0, 8))

    def choose_input(self):
        selected = filedialog.askopenfilename(title="Select input file")
        if selected:
            self.input_file.set(selected)

    def choose_output(self):
        selected = filedialog.askdirectory(title="Select output folder")
        if selected:
            self.output_folder.set(selected)

    def choose_cli(self):
        selected = filedialog.askopenfilename(
            title="Select cli.lua from the Prometheus checkout root",
            filetypes=[("Lua", "*.lua"), ("All files", "*.*")],
        )
        if not selected:
            return
        error = cli_checkout_error(selected)
        if error:
            messagebox.showerror("Prometheus checkout", error)
            self.write_log(error)
            return
        self.cli_path.set(selected)
        self.write_log("Prometheus cli.lua set.")
        save_config(self.snapshot())

    def choose_lua(self):
        selected = filedialog.askopenfilename(
            title="Select the Lua executable",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if selected:
            self.lua_bin.set(selected)
            save_config(self.snapshot())

    def choose_bash(self):
        selected = filedialog.askopenfilename(
            title="Select Cygwin bash.exe",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if not selected:
            return
        if not is_cygwin_bash(selected):
            messagebox.showerror(
                "Cygwin bash",
                "That file is not Cygwin bash. Pick bash.exe from the Cygwin bin folder.",
            )
            return
        self.cygwin_bash.set(selected)
        save_config(self.snapshot())

    def maybe_prompt_cli(self):
        if cli_checkout_error(self.cli_path.get()) is None:
            return
        self.write_log("Select the cli.lua at the root of your Prometheus checkout.")
        self.choose_cli()

    def update_output_filename(self, *_):
        input_path = self.input_file.get().strip()
        output_folder = self.output_folder.get().strip()
        if input_path and output_folder:
            filename = f"{Path(input_path).stem}.obfuscate.lua"
            self.output_file.set(str(Path(output_folder) / filename))
            return
        self.output_file.set("")

    def write_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def run(self):
        input_path = self.input_file.get().strip()
        output_path = self.output_file.get().strip()
        preset = self.preset.get().strip()
        luaver = self.luaver.get().strip()
        if not os.path.isfile(input_path):
            messagebox.showerror("Input required", "Select an existing input file.")
            return
        if not os.path.isdir(self.output_folder.get().strip()):
            messagebox.showerror("Output required", "Select an existing output folder.")
            return
        if preset not in PRESETS:
            messagebox.showerror("Preset required", "Choose a preset.")
            return
        if luaver not in LUA_VERSIONS:
            messagebox.showerror("Version required", "Choose Lua51 or LuaU.")
            return
        if cli_checkout_error(self.cli_path.get()) is not None and not self.cli_path.get().strip():
            self.choose_cli()
        cli_error = cli_checkout_error(self.cli_path.get())
        if cli_error:
            messagebox.showerror("Prometheus checkout", cli_error)
            return
        save_config(self.snapshot())
        self.run_button.configure(state="disabled")
        self.write_log("Starting…")
        threading.Thread(
            target=self._run_process,
            args=(input_path, output_path, preset, luaver),
            daemon=True,
        ).start()

    def _run_process(self, input_path, output_path, preset, luaver):
        try:
            runtime = resolve_runtime(
                self.cli_path.get(),
                self.lua_bin.get(),
                self.cygwin_bash.get(),
            )
            if runtime.mode == "missing" or not runtime.lua:
                self.events.put(("error", runtime.error or "Lua interpreter not found."))
                return
            if runtime.error:
                self.events.put(("error", runtime.error))
                return
            self.events.put(("log", f"Using {runtime.mode} Lua."))
            code = run_prometheus(
                runtime,
                input_path,
                output_path,
                preset,
                luaver,
                lambda line: self.events.put(("log", line)),
            )
            self.events.put(("done", code))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def _notify(self, title, message, is_error=False):
        if winsound is not None:
            try:
                winsound.MessageBeep(
                    winsound.MB_ICONHAND if is_error else winsound.MB_ICONASTERISK)
            except RuntimeError:
                self.bell()
        else:
            self.bell()
        popup = tk.Toplevel(self)
        popup.title(title)
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        frame = ttk.Frame(popup, padding=16)
        frame.grid()
        ttk.Label(frame, text=message, wraplength=320, justify="left").grid(row=0, column=0)
        popup.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - popup.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - popup.winfo_height()) // 2
        popup.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        popup.after(3000, popup.destroy)

    def _poll_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self.write_log(value)
                elif kind == "done":
                    self.run_button.configure(state="normal")
                    if value == 0:
                        self.write_log("Finished successfully.")
                        self._notify("Prometheus Launcher", "Finished successfully.")
                    else:
                        self.write_log(f"Finished with exit code {value}.")
                        self._notify(
                            "Prometheus Launcher",
                            f"Prometheus failed (exit code {value}). See the log.",
                            is_error=True,
                        )
                elif kind == "error":
                    self.run_button.configure(state="normal")
                    self.write_log("Error: " + value)
                    self._notify("Prometheus Launcher", value, is_error=True)
        except queue.Empty:
            pass
        self.after(100, self._poll_events)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--check" in args:
        return write_check(args)
    Launcher().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
