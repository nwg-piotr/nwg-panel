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
    data = {}
    old_data = {}

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
            subprocess.Popen(autostart, shell=True)

    # remove stale data file, if any
    if os.path.isfile(output_file):
        os.remove(output_file)

    # read stdin, parse data, save in json format
    for line in fileinput.input():
        parts = line.split()

        output = parts[0]
        if output not in data:
            data[output] = {}

        if parts[1] == "title" and len(parts) == 3:
            data[output]["title"] = parts[2]

        if parts[1] == "tags":
            data[output]["tags"] = line.split("{} tags".format(output))[1].strip()

        elif parts[1] == "layout":
            data[output]["layout"] = parts[2]

        #if old_data != data:
        with open(output_file, 'w') as fp:
            json.dump(data, fp, indent=4)

            #old_data = data.copy()


if __name__ == '__main__':
    main()
