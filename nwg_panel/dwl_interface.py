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
from time import sleep


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
    refresh_signal = os.getenv("SIG") if os.getenv("SIG") else 10

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

            subprocess.Popen("pkill -f -{} nwg-panel".format(refresh_signal), shell=True)
            cnt = 0


if __name__ == '__main__':
    main()
