#!/usr/bin/env python3

import os
sway = False

i3 = None

ipc_data = None

outputs = {}
outputs_num = 0
windows_list = []
taskbars_list = []
scratchpads_list = []
workspaces_list = []
controls_list = []
config_dir = ""
app_dirs = []

commands = {
    "light": False,
    "pamixer": False,
    "pactl": False,
    "playerctl": False,
    "netifaces": False,
    "pybluez": False,
    "wlr-randr": False
}

icons_path = ""  # "icons_light", "icons_dark" or "" (GTK icons)

defaults = {}
