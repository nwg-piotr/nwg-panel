#!/usr/bin/env python3

import os
import json

from types import SimpleNamespace

import gi
gi.require_version('GdkPixbuf', '2.0')

from types import SimpleNamespace


def get_config_dir():
    # Determine config dir path, create if not found, then create sub-dirs
    xdg_config_home = os.getenv('XDG_CONFIG_HOME')
    config_home = xdg_config_home if xdg_config_home else os.path.join(os.getenv("HOME"), ".config")
    config_dir = os.path.join(config_home, "nwg-panel")
    if not os.path.isdir(config_dir):
        print("Creating '{}'".format(config_dir))
        os.mkdir(config_dir)

    # Icon folders to store user-defined icon replacements
    icon_folder = os.path.join(config_dir, "icons_light")
    if not os.path.isdir(icon_folder):
        print("Creating '{}'".format(icon_folder))
        os.mkdir(icon_folder)

    icon_folder = os.path.join(config_dir, "icons_dark")
    if not os.path.isdir(os.path.join(icon_folder)):
        print("Creating '{}'".format(icon_folder))
        os.mkdir(icon_folder)

    return config_dir


def load_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(e)
        return {}


def save_json(src_dict, path):
    with open(path, 'w') as f:
        json.dump(src_dict, f, indent=2)


def save_string(string, file):
    try:
        file = open(file, "wt")
        file.write(string)
        file.close()
    except:
        print("Error writing file '{}'".format(file))


def sample_config():
    config = []
    panel = {}
    panel["output"] = "eDP-1"
    panel["layer"] = "top"
    panel["position"] = "bottom"
    panel["margin-top"] = 0
    panel["margin-bottom"] = 0
    panel["padding-horizontal"] = 0
    panel["padding-vertical"] = 0
    panel["spacing"] = 0
    panel["modules-left"] = ["workspaces"]
    panel["modules-center"] = []
    panel["modules-right"] = []
    panel["workspaces"] = {"show-app-icon": True, "show-split": True, "show-app-name": True, "name-max-len": 30}

    config.append(panel)

    panel = {}
    panel["output"] = "HDMI-A-1"
    panel["layer"] = "top"
    panel["position"] = "bottom"
    panel["margin-top"] = 0
    panel["margin-bottom"] = 0
    panel["padding-horizontal"] = 0
    panel["padding-vertical"] = 0
    panel["modules-left"] = ["workspaces"]
    panel["modules-center"] = []
    panel["modules-right"] = []
    panel["workspaces"] = {"max_length": 30, "show-icon": True, "rename": True}

    config.append(panel)

    return config
