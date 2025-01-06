import json
import subprocess
from typing import Dict

import gi

gi.require_version("Gdk", "3.0")
from gi.repository import Gdk


# IDC,  screen.get_monitor_plug_name is deprecated
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

display: Gdk.Display = Gdk.Display.get_default()
screen: Gdk.Screen = Gdk.Display.get_default().get_default_screen()


def get_all_monitors() -> Dict:
    monitors = json.loads(subprocess.check_output(["hyprctl", "monitors", "-j"]))
    return {monitor["id"]:monitor["name"] for monitor in monitors}

def get_hyprctl_monitor_id_from_name(monitor_name: str) -> int | None:
    monitors = get_all_monitors()
    for id, name in monitors.items():
        if name == monitor_name:
            return id
    raise ValueError(f"Monitor {monitor_name} not found")

def get_gdk_monitor_id_from_name(plug_name: str) -> int | None:
    for i in range(display.get_n_monitors()):
        if screen.get_monitor_plug_name(i) == plug_name:
            return i
    return None


def get_gdk_monitor_id(hyprland_id: int) -> int | None:
    monitors = get_all_monitors()
    if hyprland_id in monitors:
        return get_gdk_monitor_id_from_name(monitors[hyprland_id])
    return None


def get_current_gdk_monitor_id() -> int | None:
    active_workspace = json.loads(
        subprocess.check_output(["hyprctl", "activeworkspace", "-j"])
    )
    return get_gdk_monitor_id_from_name(active_workspace["monitor"])