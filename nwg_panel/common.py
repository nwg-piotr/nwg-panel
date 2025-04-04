#!/usr/bin/env python3

sway = False

i3 = None

outputs = {}
mon_desc2output_name = {}  # {'Samsung Electric Company SyncMaster 0x4B493234': 'HDMI-A-1', (...)}
outputs_num = 0
windows_list = []
h_taskbars_list = []
h_workspaces_list = []
h_submaps_list = []
niri_taskbars_list = []
controls_list = []
executors_list = []
tray_list = []
config_dir = ""
dwl_data_file = None
dwl_instances = []
name2icon_dict = {}
scratchpad_cons = {}

commands = {
    "light": False,
    "brightnessctl": False,
    "ddcutil": False,
    "pamixer": False,
    "pactl": False,
    "playerctl": False,
    "wlr-randr": False,
    "hyprctl": False,
    "upower": False,
    "swaync": False
}

icons_path = ""  # "icons_light", "icons_dark" or "" (GTK icons)

defaults = {}
