#!/usr/bin/env python3

from i3ipc import Connection

i3 = Connection()
ipc_data = None

outputs = {}
taskbars_list = []
config_dir = ""
app_dirs = []

key_missing = False

dependencies = {
    "pyalsa": False,
    "upower": False,
    "acpi": False,
    "netifaces": False,
}

icons_path = "icons_light"   # "icons_light", "icons_dark" or "" (GTK icons)

commands = {
    "get_battery": "upower -i $(upower -e | grep BAT) | grep --color=never -E 'state|to\\\\ full|to\\\\ empty|percentage'",
    "get_battery_alt": "acpi",
    "get_bt_name": "bluetoothctl show | awk '/Name/{print $2}'",
    "get_bt_status": "bluetoothctl show | awk '/Powered/{print $2}'",
    "get_brightness": "light -G",
    "get_host": "uname -n",
    "get_ssid": "iwgetid -r",
    "get_user": "echo $USER",
    "get_volume_alt": "amixer sget Master",
    "set_brightness": "light -S",
    "set_volume_alt": "amixer sset Master",
    "systemctl": "systemctl",
    "playerctl": "playerctl"
  }
