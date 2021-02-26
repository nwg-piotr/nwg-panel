#!/usr/bin/env python3

import os
sway = False

if os.getenv('SWAYSOCK') is not None:
    from i3ipc import Connection
    i3 = Connection()

ipc_data = None

outputs = {}
windows_list = []
taskbars_list = []
scratchpads_list = []
controls_list = []
config_dir = ""
app_dirs = []

dependencies = {
    "pyalsa": False,
    "netifaces": False,
    "amixer": False
}

icons_path = ""  # "icons_light", "icons_dark" or "" (GTK icons)

scontrol = "Master"
