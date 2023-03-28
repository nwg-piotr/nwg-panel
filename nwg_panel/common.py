#!/usr/bin/env python3

sway = False

i3 = None

ipc_data = None

outputs = {}
outputs_num = 0
windows_list = []
taskbars_list = []
h_taskbars_list = []
scratchpads_list = []
workspaces_list = []
controls_list = []
executors_list = []
tray_list = []
config_dir = ""
dwl_data_file = None
dwl_instances = []
app_dirs = []
name2icon_dict = {}
scratchpad_cons = {}

commands = {
    "light": False,
    "brightnessctl": False,
    "ddcutil": False,
    "pamixer": False,
    "pactl": False,
    "playerctl": False,
    "netifaces": False,
    "btmgmt": False,
    "wlr-randr": False,
    "upower": False,
    "swaync": False
}

icons_path = ""  # "icons_light", "icons_dark" or "" (GTK icons)

defaults = {}
