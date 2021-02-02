#!/usr/bin/python3

import os
import sys
import json

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from nwg_panel.tools import get_config_dir, load_json, list_outputs, check_key, is_command, list_configs

config_dir = get_config_dir()
configs = {}


def main():
    global configs
    configs = list_configs(config_dir)
            
    for key in configs:
        panels = configs[key]
        print("File: {}".format(key))
        for panel in panels:
            check_key(panel, "name", "")
            print("Name: '{}', Output: '{}', position: '{}'".format(panel["name"], panel["output"], panel["position"]))
        print()


if __name__ == "__main__":
    sys.exit(main())
