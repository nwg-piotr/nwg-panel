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
dwl_data_file = None
dwl_instances = []
app_dirs = []
name2icon_dict = {}

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
