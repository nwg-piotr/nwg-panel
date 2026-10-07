#!/usr/bin/env python3

"""
This command has two purposes:

1. Execute commands from ~./config/nwg-panel/autostart-dwl.sh file (if found);
2. save data provided by dwl (title, tags, layout for each output) to the cache file
   in json format, for further use by the dwl module.

You need to start dwl with `dwl -s nwg-dwl-interface`.
"""

import subprocess
import fileinput
import os
import sys
import json
import signal
from time import sleep


_panel_pids = {}  # PID -> start time


def is_panel_cmdline(argv):
    """
    Tells if a command line (list of strings) is the one of a running panel: `nwg-panel ...`,
    `python3 /usr/bin/nwg-panel ...`, a wrapped install (`.nwg-panel-wrapped`), `python3 -m nwg_panel.main` or
    `python3 /some/path/nwg_panel/main.py`. "nwg-panel" somewhere in the command line is not enough: that also
    matches `nwg-panel-config`, `tail -f ~/.config/nwg-panel/style.css` or `earlyoom --avoid nwg-panel`.
    """
    if not argv:
        return False
    names = ("nwg-panel", ".nwg-panel-wrapped")
    if os.path.basename(argv[0]) in names:
        return True
    if not os.path.basename(argv[0]).startswith("python"):
        return False
    # what the interpreter runs: the 1st argument after its options, of which -W and -X take a value
    args = argv[1:]
    while args and args[0].startswith("-") and args[0] != "-m":
        args = args[2:] if args[0] in ("-W", "-X") else args[1:]
    if args[:1] == ["-m"]:
        return args[1:2] == ["nwg_panel.main"]
    path, script = os.path.split(args[0]) if args else ("", "")
    return script in names or (script == "main.py" and os.path.basename(path) == "nwg_panel")


def start_time(pid):
    """Start time of a process (field 22 of /proc/<pid>/stat), None if it's gone."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            # the 2nd field, (comm), may contain spaces and parentheses: count from the last ")"
            return f.read().rsplit(b")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def panel_pids():
    """PIDs of our running nwg-panel instances (cached; the /proc scan only happens when they change)."""
    global _panel_pids
    # a cached PID is only trusted if it still belongs to the same process: once the panel is gone, its PID may
    # be given to anything, and our signal would terminate it
    alive = [pid for pid in _panel_pids if start_time(pid) == _panel_pids[pid]]
    if alive:
        return alive

    _panel_pids = {}
    uid = os.getuid()
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            if os.stat(f"/proc/{entry}").st_uid != uid:
                continue
            started = start_time(entry)
            with open(f"/proc/{entry}/cmdline", "rb") as f:
                argv = f.read().decode("utf-8", errors="replace").split("\0")
        except OSError:
            continue
        if started and is_panel_cmdline(argv):
            _panel_pids[int(entry)] = started
    return list(_panel_pids)


def parse_signal(value):
    """
    Signal number from the `SIG` variable, None if invalid. The value used to be handed over to `pkill -<SIG>`:
    like there, it may be a number or a name, with or without the SIG prefix (USR1, SIGUSR2, RTMIN+1, RTMAX-2).
    """
    name = str(value).strip().upper()
    if name.startswith("SIG"):
        name = name[3:]
    try:
        if name.isdigit():
            sig = int(name)
        elif name.startswith("RTMIN+"):
            sig = signal.SIGRTMIN + int(name[6:])
        elif name.startswith("RTMAX-"):
            sig = signal.SIGRTMAX - int(name[6:])
        else:
            sig = int(signal.Signals["SIG" + name])
    except (KeyError, ValueError):
        return None
    return sig if sig in signal.valid_signals() else None


def is_command(cmd):
    cmd = cmd.split()[0]  # strip arguments
    cmd = "command -v {}".format(cmd)
    try:
        is_cmd = subprocess.check_output(cmd, shell=True).decode("utf-8").strip()
        if is_cmd:
            return True

    except subprocess.CalledProcessError:
        return False


def list_outputs():
    print("Checking outputs...")
    outputs = []
    if is_command("wlr-randr"):
        lines = subprocess.check_output("wlr-randr", shell=True).decode("utf-8").strip().splitlines()
        for line in lines:
            if not line.startswith(" "):
                name = line.split()[0]
                print(name)
                outputs.append(name)
    else:
        print("Missing wlr-randr dependency")
    return outputs


def get_cache_dir():
    if os.getenv("XDG_CACHE_HOME"):
        return os.getenv("XDG_CACHE_HOME")
    elif os.getenv("HOME") and os.path.isdir(os.path.join(os.getenv("HOME"), ".cache")):
        return os.path.join(os.getenv("HOME"), ".cache")
    else:
        return None


def get_config_dir():
    xdg_config_home = os.getenv('XDG_CONFIG_HOME')
    config_home = xdg_config_home if xdg_config_home else os.path.join(os.getenv("HOME"), ".config")
    config_dir = os.path.join(config_home, "nwg-panel")
    if os.path.isdir(config_dir):
        return config_dir
    else:
        return None


def main():
    refresh_signal = parse_signal(os.getenv("SIG")) if os.getenv("SIG") else 10
    if refresh_signal is None:
        # not fatal: autostart-dwl.sh has to run and the data file to be written all the same
        print("Invalid signal SIG={}: expected a number or a name such as USR1 or RTMIN+1. "
              "The panel will not be told to refresh.".format(os.getenv("SIG")))

    outputs = list_outputs()
    if len(outputs) > 0:
        num_lines = len(outputs) * 4
    else:
        print("No output detected, terminating")
        sys.exit(1)

    data = {}

    # Determine output file location
    cache_dir = get_cache_dir()
    if not cache_dir:
        print("Couldn't detect cache directory")
        sys.exit(1)
    else:
        output_file = os.path.join(cache_dir, "nwg-dwl-data")

    # Run autostart script if present
    config_dir = get_config_dir()
    if not config_dir:
        print("Couldn't detect nwg-panel config directory")
    else:
        autostart = os.path.join(config_dir, "autostart-dwl.sh")
        if os.path.isfile(autostart):
            print("Running {}".format(autostart))
            os.system(autostart)

        sleep(1)

    # remove stale data file, if any
    if os.path.isfile(output_file):
        os.remove(output_file)

    # read stdin, parse data, save in json format
    cnt = 0
    print("num_lines = {}".format(num_lines))
    for line in fileinput.input():
        parts = line.split()

        output = parts[0]
        if output not in data:
            data[output] = {}

        if parts[1] == "title":
            if len(parts) >= 3:
                title = ' '.join(parts[2:])
                if "title" not in data[output] or data[output]["title"] != title:
                    data[output]["title"] = title
            else:
                if "title" not in data[output] or data[output]["title"] != "":
                    data[output]["title"] = ""

        elif parts[1] == "selmon":
            if "selmon" not in data[output] or data[output]["selmon"] != parts[2]:
                data[output]["selmon"] = parts[2]

        elif parts[1] == "tags":
            tags = line.split("{} tags".format(output))[1].strip()
            if "tags" not in data[output] or data[output]["tags"] != tags:
                data[output]["tags"] = tags

        elif parts[1] == "layout":
            if "layout" not in data[output] or data[output]["layout"] != parts[2]:
                data[output]["layout"] = parts[2]

        cnt += 1

        if cnt == num_lines:
            with open(output_file, 'w') as fp:
                json.dump(data, fp, indent=4)

            # was `pkill -f -SIG nwg-panel`: 2 forks per update, and SIGUSR1 (default action: terminate)
            # sent to any process whose command line merely contains "nwg-panel"
            if refresh_signal is not None:
                for pid in panel_pids():
                    try:
                        os.kill(pid, refresh_signal)
                    except OSError:
                        pass
            cnt = 0


if __name__ == '__main__':
    main()
