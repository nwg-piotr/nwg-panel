#!/usr/bin/python3

"""
GTK3-based panel for sway Wayland compositor
Project: https://github.com/nwg-piotr/nwg-panel
Author's email: nwg.piotr@gmail.com
Copyright (c) 2021-2023 Piotr Miller & Contributors
License: MIT
"""
import argparse
import os
import signal
import sys
import threading

import gi

from nwg_panel.__about__ import __version__

gi.require_version('Gtk', '3.0')
try:
    gi.require_version('GtkLayerShell', '0.1')
except ValueError:

    raise RuntimeError('\n\n' +
                       'If you haven\'t installed GTK Layer Shell, you need to point Python to the\n' +
                       'library by setting GI_TYPELIB_PATH and LD_LIBRARY_PATH to <build-dir>/src/.\n' +
                       'For example you might need to run:\n\n' +
                       'GI_TYPELIB_PATH=build/src LD_LIBRARY_PATH=build/src python3 ' + ' '.join(sys.argv))

from gi.repository import GtkLayerShell, GLib

try:
    import psutil
except ModuleNotFoundError:
    print("You need to install python-psutil package")
    sys.exit(1)

from nwg_panel.tools import *

from nwg_panel.modules.custom_button import CustomButton
from nwg_panel.modules.executor import Executor
from nwg_panel.modules.clock import Clock
from nwg_panel.modules.controls import Controls
from nwg_panel.modules.playerctl import Playerctl
from nwg_panel.modules.cpu_avg import CpuAvg
from nwg_panel.modules.scratchpad import Scratchpad
from nwg_panel.modules.dwl_tags import DwlTags
from nwg_panel.modules.swaync import SwayNC
from nwg_panel.modules.sway_mode import SwayMode
from nwg_panel.modules.keyboard_layout import KeyboardLayout

try:
    from nwg_panel.modules.openweather import OpenWeather
except Exception as e:
    eprint("Couldn't load OpenWeather module: ".format(e))
from nwg_panel.modules.brightness_slider import BrightnessSlider

from nwg_panel.modules.menu_start import MenuStart

dir_name = os.path.dirname(__file__)

from nwg_panel import common

tray_available = False
try:
    from nwg_panel.modules import sni_system_tray

    tray_available = True
except:
    eprint("Couldn't load system tray, is 'python-dasbus' installed?")

sway = os.getenv('SWAYSOCK') is not None
if sway:
    try:
        import i3ipc
        from i3ipc import Connection, Event
    except ModuleNotFoundError:
        eprint("'python-i3ipc' package required on sway, terminating")
        sys.exit(1)

    common.i3 = Connection()
    from nwg_panel.modules.sway_taskbar import SwayTaskbar
    from nwg_panel.modules.sway_workspaces import SwayWorkspaces

his = os.getenv('HYPRLAND_INSTANCE_SIGNATURE')
if his:
    from nwg_panel.modules.hyprland_taskbar import HyprlandTaskbar
    from nwg_panel.modules.hyprland_workspaces import HyprlandWorkspaces

common_settings = {}
restart_cmd = ""
sig_dwl = 0
voc = {}

panel_windows_hide_show_sigs = {}


def load_vocabulary():
    global voc
    # basic vocabulary (for en_US)
    voc = load_json(os.path.join(dir_name, "langs", "en_US.json"))
    if not voc:
        eprint("Failed loading vocabulary")
        sys.exit(1)

    shell_data = load_shell_data()
    lang = os.getenv("LANG").split(".")[0] if not shell_data["interface-locale"] else shell_data["interface-locale"]
    # translate if translation available
    if lang != "en_US":
        loc_file = os.path.join(dir_name, "langs", "{}.json".format(lang))
        if os.path.isfile(loc_file):
            # localized vocabulary
            loc = load_json(loc_file)
            if not loc:
                eprint("Failed loading translation into '{}'".format(lang))
            else:
                for key in loc:
                    voc[key] = loc[key]


def signal_handler(sig, frame):
    global sig_dwl
    desc = {2: "SIGINT", 15: "SIGTERM", 10: "SIGUSR1"}
    if sig == 2 or sig == 15:
        print("Terminated with {}".format(desc[sig]))
        if tray_available:
            sni_system_tray.deinit_tray()
        Gtk.main_quit()
    elif sig == sig_dwl:
        refresh_dwl()
    else:
        return


def rt_sig_handler(sig, frame):
    print("{} RT signal received".format(sig))
    for executor in common.executors_list:
        if executor.use_sigrt and executor.sigrt == sig:
            eprint("Refreshing {} on signal {}".format(executor.name, sig))
            executor.refresh()

    for win in panel_windows_hide_show_sigs:
        if sig == panel_windows_hide_show_sigs[win]:
            if win.is_visible():
                win.hide()
            else:
                win.show_all()


def restart():
    subprocess.Popen(restart_cmd, shell=True)


def hypr_watcher():
    import socket

    # /tmp/hypr moved to $XDG_RUNTIME_DIR/hypr in #5788
    xdg_runtime_dir = os.getenv("XDG_RUNTIME_DIR")
    hypr_dir = f"{xdg_runtime_dir}/hypr" if xdg_runtime_dir and os.path.isdir(
        f"{xdg_runtime_dir}/hypr") else "/tmp/hypr"

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(f"{hypr_dir}/{his}/.socket2.sock")
    just_refreshed = False

    while True:
        datagram = client.recv(2048)
        e_full_string = datagram.decode('utf-8').strip()
        lines = e_full_string.splitlines()

        event_names = []
        for line in lines:
            event_names.append(line.split(">>")[0])
        # print(f"events: {event_names}")

        for event_name in event_names:
            if event_name in ["activespecial",
                              "activewindow",
                              "activewindowv2",
                              "changefloatingmode",
                              "closewindow",
                              "createworkspace",
                              "destroyworkspace",
                              "focusedmon",
                              "monitoradded",
                              "movewindow",
                              "openwindow",
                              "windowtitle",
                              "workspace"]:

                if "activewindow" in event_name and just_refreshed:
                    just_refreshed = False
                    break

                # print(f">>> refreshing on {event_name}")
                monitors, workspaces, clients, activewindow, activeworkspace = h_modules_get_all()
                for item in common.h_taskbars_list:
                    GLib.timeout_add(0, item.refresh, monitors, workspaces, clients, activewindow)

                for item in common.h_workspaces_list:
                    GLib.timeout_add(0, item.refresh, monitors, workspaces, clients, activewindow, activeworkspace)

                if event_name in ["createworkspace", "destroyworkspace", "focusedmon", "workspace"]:
                    just_refreshed = True
                break


def on_i3ipc_event(i3conn, event):
    if common_settings["restart-on-display"]:
        num = num_active_outputs(i3conn.get_outputs())
        if num > common.outputs_num:
            print("Number of outputs increased ({}); restart in {} ms.".format(
                num, common_settings["restart-delay"]))
            GLib.timeout_add(common_settings["restart-delay"],
                             restart,
                             priority=GLib.PRIORITY_HIGH)
        common.outputs_num = num

    GLib.idle_add(hide_controls_popup, priority=GLib.PRIORITY_HIGH)


def hide_controls_popup():
    for item in common.controls_list:
        if item.popup_window.get_visible():
            item.popup_window.hide_and_clear_tag()


def refresh_dwl(*args):
    if len(common.dwl_instances) > 0:
        dwl_data = load_json(common.dwl_data_file)
        if dwl_data:
            for item in common.dwl_instances:
                item.refresh(dwl_data)


def instantiate_content(panel, container, content_list, icons_path=""):
    check_key(panel, "position", "top")
    check_key(panel, "items-padding", 0)

    for item in content_list:
        # list initial data for Hyprland modules
        if his:
            if "hyprland-workspaces" in content_list or "hyprland-taskbar" in content_list:
                monitors, workspaces, clients, activewindow, activeworkspace = h_modules_get_all()
            else:
                monitors, workspaces, clients, activewindow, activeworkspace = {}, {}, {}, {}, {}

        if item == "sway-taskbar":
            if "sway-taskbar" in panel:
                if sway:
                    check_key(panel["sway-taskbar"], "all-outputs", False)
                    if panel["sway-taskbar"]["all-outputs"] or "output" not in panel:
                        taskbar = SwayTaskbar(panel["sway-taskbar"], common.i3, panel["position"],
                                              icons_path=icons_path)
                    else:
                        taskbar = SwayTaskbar(panel["sway-taskbar"], common.i3, panel["position"],
                                              display_name="{}".format(panel["output"]), icons_path=icons_path)

                    container.pack_start(taskbar, False, False, panel["items-padding"])
                else:
                    eprint("'sway-taskbar' ignored")
            else:
                eprint("'sway-taskbar' not defined in this panel instance")

        if item == "sway-workspaces":
            if sway:
                if "sway-workspaces" in panel:
                    workspaces = SwayWorkspaces(panel["sway-workspaces"], common.i3, icons_path=icons_path)
                    container.pack_start(workspaces, False, False, panel["items-padding"])
                else:
                    print("'sway-workspaces' not defined in this panel instance")
            else:
                eprint("'sway-workspaces' ignored")

        if item == "scratchpad":
            if sway:
                # Added in v0.1.3, so may be undefined in user's config.
                if item not in panel:
                    panel["scratchpad"] = {}
                scratchpad = Scratchpad(common.i3, common.i3.get_tree(), panel[item], panel["output"],
                                        icons_path=icons_path)
                container.pack_start(scratchpad, False, False, panel["items-padding"])
            else:
                eprint("'scratchpad' ignored")

        if item == "sway-mode":
            if sway:
                if item not in panel:
                    panel["sway-mode"] = {}
                sway_mode = SwayMode(common.i3, panel[item], icons_path=icons_path)
                container.pack_start(sway_mode, False, False, panel["items-padding"])
            else:
                eprint("'sway-mode' ignored")

        if item == "hyprland-taskbar":
            if "hyprland-taskbar" in panel:
                if panel["layer"] in ["bottom", "background"]:
                    eprint(
                        "Panel '{}': On Hyprland, panels must be placed on 'top' or 'overlay' layer, but '{}' found in "
                        "settings. Changing to 'top'.".format(panel["name"], panel["layer"]))
                    panel["layer"] = "top"  # or context menu will remain invisible
                if his:
                    check_key(panel["hyprland-taskbar"], "all-outputs", False)
                    if panel["hyprland-taskbar"]["all-outputs"] or "output" not in panel:
                        taskbar = HyprlandTaskbar(panel["hyprland-taskbar"], panel["position"], monitors, workspaces,
                                                  clients, activewindow, icons_path=icons_path)
                    else:
                        taskbar = HyprlandTaskbar(panel["hyprland-taskbar"], panel["position"], monitors, workspaces,
                                                  clients, activewindow, display_name="{}".format(panel["output"]),
                                                  icons_path=icons_path)

                    common.h_taskbars_list.append(taskbar)
                    container.pack_start(taskbar, False, False, panel["items-padding"])
                else:
                    eprint("'hyprland-taskbar' ignored (HIS unknown).")

        if item == "hyprland-workspaces":
            if his:
                if "hyprland-workspaces" in panel:
                    workspaces = HyprlandWorkspaces(panel["hyprland-workspaces"], monitors, workspaces, clients,
                                                    activewindow, activeworkspace, icons_path=icons_path)
                    container.pack_start(workspaces, False, False, panel["items-padding"])
                    common.h_workspaces_list.append(workspaces)
                else:
                    print("'hyprland-workspaces' not defined in this panel instance")
            else:
                eprint("'hyprland-workspaces' ignored")

        if item == "keyboard-layout":
            if his or sway:
                if "keyboard-layout" not in panel:
                    panel["keyboard-layout"] = {}
                kb_layout = KeyboardLayout(panel["keyboard-layout"], icons_path)
                container.pack_start(kb_layout, False, False, panel["items-padding"])
            else:
                eprint("KeyboardLayout module does not yet support sway")

        if "button-" in item:
            if item in panel:
                button = CustomButton(panel[item], icons_path)
                container.pack_start(button, False, False, panel["items-padding"])
            else:
                print("'{}' not defined in this panel instance".format(item))

        if "executor-" in item:
            if item in panel:
                executor = Executor(panel[item], icons_path, item)
                container.pack_start(executor, False, False, panel["items-padding"])
                common.executors_list.append(executor)
            else:
                print("'{}' not defined in this panel instance".format(item))

        if item == "clock":
            if item in panel:
                clock = Clock(panel[item], icons_path=icons_path)
                container.pack_start(clock, False, False, panel["items-padding"])
            else:
                clock = Clock({})
                container.pack_start(clock, False, False, 0)

        if item == "playerctl":
            if item in panel:
                playerctl = Playerctl(panel[item], voc, icons_path)
                container.pack_start(playerctl, False, False, panel["items-padding"])
            else:
                print("'{}' not defined in this panel instance".format(item))

        if item == "openweather":
            if "python-requests" in common.commands and common.commands["python-requests"]:
                if item in panel:
                    openweather = OpenWeather(panel[item], voc, icons_path=icons_path)
                    container.pack_start(openweather, False, False, panel["items-padding"])
            else:
                eprint("OpenWeather module needs the 'python-requests' package")

        if item == "brightness-slider":
            if item in panel:
                brightness_slider = BrightnessSlider(panel[item], icons_path)
                container.pack_start(brightness_slider, False, False, panel["items-padding"])

        if item == "cpu-avg":
            cpu_avg = CpuAvg()
            container.pack_start(cpu_avg, False, False, panel["items-padding"])

        if item == "dwl-tags":
            if os.path.isfile(common.dwl_data_file):
                if "dwl-tags" not in panel:
                    panel["dwl-tags"] = {}

                dwl_tags = DwlTags(panel["output"], panel["dwl-tags"])
                common.dwl_instances.append(dwl_tags)
                container.pack_start(dwl_tags, False, False, panel["items-padding"])
                dwl_data = load_json(common.dwl_data_file)
                if dwl_data:
                    dwl_tags.refresh(dwl_data)
            else:
                eprint("{} data file not found".format(common.dwl_data_file))

        if item == "tray" and tray_available:
            tray_settings = {}
            if "tray" in panel:
                tray_settings = panel["tray"]
            tray = sni_system_tray.Tray(tray_settings, panel["position"], icons_path)
            common.tray_list.append(tray)
            container.pack_start(tray, False, False, panel["items-padding"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c",
                        "--config",
                        type=str,
                        default="config",
                        help="config filename (in {}/)".format(common.config_dir))

    parser.add_argument("-s",
                        "--style",
                        type=str,
                        default="style.css",
                        help="css filename (in {}/)".format(common.config_dir))

    parser.add_argument("-sigdwl",
                        type=int,
                        default=10,
                        help="signal to refresh dwl-tags module; default: 10 (SIGUSR1)")

    parser.add_argument("-r",
                        "--restore",
                        action="store_true",
                        help="restore default config files")

    parser.add_argument("-v",
                        "--version",
                        action="version",
                        version="%(prog)s version {}".format(__version__),
                        help="display version information")

    args = parser.parse_args()

    # Kill running instances, if any
    own_pid = os.getpid()
    # We should never have more that 1, but just in case
    running_instances = []

    for proc in psutil.process_iter():
        # kill 'nwg-panel', don't kill 'nwg-panel-config'
        if "nwg-panel" in proc.name() and "-con" not in proc.name():
            pid = proc.pid
            if pid != own_pid:
                running_instances.append(pid)
                # The easy way: try SIGINT, which we handle gentle
                print("Running instance found, PID {}, sending SIGINT".format(pid))
                os.kill(pid, signal.SIGINT)

    # Give it half a second to die
    time.sleep(0.5)

    # The hard way, if something's still alive ;)
    pids = psutil.pids()
    for p in running_instances:
        if p in pids:
            print("PID {} still alive, sending SIGKILL".format(p))
            os.kill(p, signal.SIGKILL)

    # If started e.g. with 'python <path>/main.py', the process won't be found by name.
    # Let's use saved PID and kill mercilessly. This should never happen in normal use.
    pid_file = os.path.join(temp_dir(), "nwg-panel.pid")
    if os.path.isfile(pid_file):
        try:
            pid = int(load_text_file(pid_file))
            os.kill(pid, signal.SIGKILL)
            print("Running no name instance killed, PID {}".format(pid))
        except:
            pass

    save_string(str(own_pid), pid_file)

    common.config_dir = get_config_dir()

    load_vocabulary()

    global common_settings
    cs_file = os.path.join(common.config_dir, "common-settings.json")
    if not os.path.isfile(cs_file):
        common_settings = {
            "restart-on-display": True,
            "restart-delay": 500,
            "processes-backgroud-only": True,
            "processes-own-only": True
        }
        save_json(common_settings, cs_file)
    else:
        common_settings = load_json(cs_file)

    print("Common settings", common_settings)

    cache_dir = get_cache_dir()
    if cache_dir:
        common.dwl_data_file = os.path.join(cache_dir, "nwg-dwl-data")
        scratchpad_file = os.path.join(temp_dir(), "nwg-scratchpad")
        if os.path.isfile(scratchpad_file):
            common.scratchpad_cons = load_json(scratchpad_file)
            eprint("Loaded scratchpad info", common.scratchpad_cons)
    else:
        eprint("Couldn't determine cache directory")

    global sig_dwl
    sig_dwl = args.sigdwl

    catchable_sigs = set(signal.Signals) - {signal.SIGKILL, signal.SIGSTOP, signal.SIGCHLD}
    for sig in catchable_sigs:
        try:
            signal.signal(sig, signal_handler)
        except Exception as exc:
            eprint("{} subscription error: {}".format(sig, exc))

    for sig in range(signal.SIGRTMIN, signal.SIGRTMAX + 1):
        try:
            signal.signal(sig, rt_sig_handler)
        except Exception as exc:
            eprint("{} subscription error: {}".format(sig, exc))

    check_commands()
    print("Dependencies check:", common.commands)

    global restart_cmd
    restart_cmd = "nwg-panel -c {} -s {}".format(args.config, args.style)

    save_string("-c {} -s {}".format(args.config, args.style), os.path.join(local_dir(), "args"))

    common.app_dirs = get_app_dirs()
    # common.name2icon_dict = map_odd_desktop_files()

    config_file = os.path.join(common.config_dir, args.config)

    copy_files(os.path.join(dir_name, "icons_light"), os.path.join(common.config_dir, "icons_light"))
    copy_files(os.path.join(dir_name, "icons_dark"), os.path.join(common.config_dir, "icons_dark"))
    copy_files(os.path.join(dir_name, "icons_color"), os.path.join(common.config_dir, "icons_color"))
    # copy_files(os.path.join(dir_name, "langs"), os.path.join(common.config_dir, "langs"))
    copy_executors(os.path.join(dir_name, "executors"), os.path.join(common.config_dir, "executors"))
    copy_files(os.path.join(dir_name, "config"), common.config_dir, args.restore)
    copy_files(os.path.join(dir_name, "local"), local_dir())

    # tree = common.i3.get_tree() if sway else None
    common.outputs, common.mon_desc2output_name = list_outputs(sway=sway)
    print(f"Outputs: {common.outputs}")
    print(f"Descriptions: {common.mon_desc2output_name}")

    panels = load_json(config_file)

    screen = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    style_context = Gtk.StyleContext()
    style_context.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    try:
        provider.load_from_path(os.path.join(common.config_dir, args.style))
    except Exception as e:
        eprint(e)

    # Controls background window (invisible): add style missing from the css file
    css = provider.to_string().encode('utf-8')
    css += b""" window#bcg-window { background-color: rgba(0, 0, 0, 0.2); } """
    provider.load_from_data(css)

    # Mirror bars to all outputs #48 (if panel["output"] == "All")
    to_remove = []
    to_append = []
    for panel in panels:
        check_key(panel, "output", "")
        check_key(panel, "monitor", "")
        if panel["monitor"]:
            try:
                panel["output"] = common.mon_desc2output_name[panel["monitor"]]
            except KeyError as err:
                eprint(f"Monitor description unknown: {err}")

        clones = []
        if panel["output"] == "All" and len(common.outputs) >= 1:
            to_remove.append(panel)
            for key in common.outputs.keys():
                clone = panel.copy()
                clone["output"] = key
                clones.append(clone)

            to_append = to_append + clones

    for item in to_remove:
        panels.remove(item)

    panels = panels + to_append

    for panel in panels:
        monitor = None
        try:
            monitor = common.outputs[panel["output"]]["monitor"]
        except KeyError:
            pass

        if panel["output"] and not monitor:
            print("Couldn't assign a Gdk.Monitor to output '{}'".format(panel["output"]))
            continue

        check_key(panel, "icons", "")
        icons_path = ""
        if panel["icons"] == "light":
            icons_path = os.path.join(common.config_dir, "icons_light")
        elif panel["icons"] == "dark":
            icons_path = os.path.join(common.config_dir, "icons_dark")

        # This is to allow width "auto" value. Actually all non-numeric values will be removed.
        if "width" in panel and not isinstance(panel["width"], int):
            panel.pop("width")

        if panel["output"] in common.outputs or not panel["output"]:
            check_key(panel, "spacing", 6)
            check_key(panel, "css-name", "")
            check_key(panel, "padding-horizontal", 0)
            check_key(panel, "padding-vertical", 0)
            check_key(panel, "sigrt", 0)  # SIGRTMIN > hide_show_sig_num <= SIGRTMAX, (0 = disabled)
            check_key(panel, "use-sigrt", False)
            check_key(panel, "start-hidden", False)

            window = Gtk.Window()
            global panel_windows_hide_show_sigs
            if panel["use-sigrt"]:
                panel_windows_hide_show_sigs[window] = panel["sigrt"]
            else:
                panel_windows_hide_show_sigs[window] = 0

            if panel["css-name"]:
                window.set_property("name", panel["css-name"])

            if "output" not in panel or not panel["output"]:
                display = Gdk.Display.get_default()
                monitor = display.get_monitor(0)
                for key in common.outputs:
                    if common.outputs[key]["monitor"] == monitor:
                        panel["output"] = key

            # Width undefined or "auto"
            if "output" in panel and panel["output"] and "width" not in panel:
                panel["width"] = common.outputs[panel["output"]]["width"]

            check_key(panel, "width", 0)
            w = panel["width"]

            check_key(panel["controls-settings"], "window-width", 0)
            controls_width = panel["controls-settings"]["window-width"] if panel["controls-settings"][
                                                                               "window-width"] > 0 else int(w / 5)
            check_key(panel, "height", 0)
            h = panel["height"]

            check_key(panel, "controls", "off")
            if panel["controls"]:
                check_key(panel, "controls-settings", {})

            if "controls-settings" in panel:
                controls_settings = panel["controls-settings"]
                check_key(controls_settings, "show-values", False)
                check_key(controls_settings, "window-margin", 0)

            check_key(panel, "menu-start", "off")
            if panel["menu-start"]:
                check_key(panel, "menu-start-settings", {})
                defaults = {
                    "cmd-lock": "swaylock -f -c 000000",
                    "cmd-logout": "swaymsg exit",
                    "cmd-restart": "systemctl reboot",
                    "cmd-shutdown": "systemctl -i poweroff",
                    "autohide": True,
                    "file-manager": "thunar",
                    "height": 0,
                    "icon-size-large": 32,
                    "icon-size-small": 16,
                    "icon-size-button": 16,
                    "margin-bottom": 0,
                    "margin-left": 0,
                    "margin-right": 0,
                    "margin-top": 0,
                    "padding": 2,
                    "terminal": "foot",
                    "width": 0
                }
                for key in defaults:
                    check_key(panel["menu-start-settings"], key, defaults[key])

            if panel["menu-start"] != "off":
                panel["menu-start-settings"]["horizontal-align"] = panel["menu-start"]

            Gtk.Widget.set_size_request(window, w, h)

            o = Gtk.Orientation.HORIZONTAL if panel["position"] == "top" or panel[
                "position"] == "bottom" else Gtk.Orientation.VERTICAL

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            hbox = Gtk.Box(orientation=o, spacing=0)
            vbox.pack_start(hbox, True, True, panel["padding-vertical"])

            check_key(panel, "modules-left", [])
            check_key(panel, "modules-center", [])
            check_key(panel, "modules-right", [])
            check_key(panel, "homogeneous", False)

            inner_box = Gtk.Box(orientation=o, spacing=0)

            # set equal columns width by default if "modules-center" not empty; this may be overridden in config
            if panel["modules-center"] and panel["homogeneous"]:
                inner_box.set_homogeneous(True)

            hbox.pack_start(inner_box, True, True, 0)
            hbox.set_property("margin-start", panel["padding-horizontal"])
            hbox.set_property("margin-end", panel["padding-horizontal"])
            hbox.set_property("margin-top", panel["padding-vertical"])
            hbox.set_property("margin-bottom", panel["padding-vertical"])

            left_box = Gtk.Box(orientation=o, spacing=panel["spacing"])
            left_box.set_property("name", "left-box")
            inner_box.pack_start(left_box, False, True, 0)
            if panel["controls"] and panel["controls"] == "left":
                monitor = None
                try:
                    monitor = common.outputs[panel["output"]]["monitor"]
                except KeyError:
                    pass

                cc = Controls(panel["controls-settings"], panel["position"], panel["controls"],
                              controls_width, monitor=monitor, icons_path=icons_path)
                common.controls_list.append(cc)
                left_box.pack_start(cc, False, False, 0)

                if common.commands["swaync"]:
                    if "swaync" not in panel:
                        panel["swaync"] = {}
                    sway_nc = SwayNC(panel["swaync"], icons_path, panel["position"])
                    left_box.pack_start(sway_nc, False, False, 0)

            if panel["menu-start"] == "left":
                ms = MenuStart(panel, icons_path=icons_path)
                left_box.pack_start(ms, False, False, 0)

            instantiate_content(panel, left_box, panel["modules-left"], icons_path=icons_path)
            print("left box created")

            center_box = Gtk.Box(orientation=o, spacing=panel["spacing"])
            center_box.set_property("name", "center-box")
            inner_box.pack_start(center_box, True, False, 0)
            check_key(panel, "modules-center", [])
            instantiate_content(panel, center_box, panel["modules-center"], icons_path=icons_path)
            print("center box created")

            right_box = Gtk.Box(orientation=o, spacing=panel["spacing"])
            right_box.set_property("name", "right-box")
            # Damn on the guy who invented `pack_start(child, expand, fill, padding)`!
            helper_box = Gtk.Box(orientation=o, spacing=0)
            helper_box.pack_end(right_box, False, False, 0)
            inner_box.pack_start(helper_box, False, True, 0)
            check_key(panel, "modules-right", [])
            instantiate_content(panel, right_box, panel["modules-right"], icons_path=icons_path)
            print("right box created")

            if panel["menu-start"] == "right":
                ms = MenuStart(panel["menu-start-settings"], icons_path=icons_path)
                right_box.pack_end(ms, False, False, 0)

            if panel["controls"] and panel["controls"] == "right":
                monitor = None
                try:
                    monitor = common.outputs[panel["output"]]["monitor"]
                except KeyError:
                    pass

                cc = Controls(panel["controls-settings"], panel["position"], panel["controls"],
                              controls_width, monitor=monitor, icons_path=icons_path)
                common.controls_list.append(cc)
                right_box.pack_end(cc, False, False, 0)

                if common.commands["swaync"]:
                    if "swaync" not in panel:
                        panel["swaync"] = {}

                    sway_nc = SwayNC(panel["swaync"], icons_path, panel["position"])
                    right_box.pack_end(sway_nc, False, False, 0)

            window.add(vbox)

            GtkLayerShell.init_for_window(window)
            GtkLayerShell.set_namespace(window, "nwg-panel")

            monitor = None
            try:
                monitor = common.outputs[panel["output"]]["monitor"]
            except KeyError:
                pass

            check_key(panel, "layer", "top")
            o = panel["output"] if "output" in panel else "undefined"
            m = panel["monitor"] if "monitor" in panel else "undefined"
            print("Panel '{}': output: {}, monitor: {}, position: {}, layer: {}, width: {}, height: {}".format(
                panel["name"], o, m,
                panel["position"],
                panel["layer"],
                panel["width"],
                panel["height"]))

            if monitor:
                GtkLayerShell.set_monitor(window, monitor)

            check_key(panel, "exclusive-zone", True)
            if panel["exclusive-zone"]:
                GtkLayerShell.auto_exclusive_zone_enable(window)

            layers = {"background": GtkLayerShell.Layer.BACKGROUND,
                      "bottom": GtkLayerShell.Layer.BOTTOM,
                      "top": GtkLayerShell.Layer.TOP,
                      "overlay": GtkLayerShell.Layer.OVERLAY}

            GtkLayerShell.set_layer(window, layers[panel["layer"]])

            """if panel["layer"] == "top":
                GtkLayerShell.set_layer(window, GtkLayerShell.Layer.TOP)
            else:
                GtkLayerShell.set_layer(window, GtkLayerShell.Layer.BOTTOM)"""

            check_key(panel, "margin-top", 0)
            GtkLayerShell.set_margin(window, GtkLayerShell.Edge.TOP, panel["margin-top"])

            check_key(panel, "margin-bottom", 0)
            GtkLayerShell.set_margin(window, GtkLayerShell.Edge.BOTTOM, panel["margin-bottom"])

            if panel["position"] == "top":
                GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.TOP, 1)
            elif panel["position"] == "bottom":
                GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.BOTTOM, 1)
            elif panel["position"] == "left":
                GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.LEFT, 1)
            elif panel["position"] == "right":
                GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.RIGHT, 1)

            if panel["use-sigrt"] and panel["start-hidden"]:
                window.hide()
            else:
                window.show_all()

    if sway:
        common.outputs_num = num_active_outputs(common.i3.get_outputs())
    else:
        common.outputs, common.mon_desc2output_name = list_outputs(sway=sway, silent=True)
        common.outputs_num = len(common.outputs)

    if sway:
        # Notice: Don't use Event.OUTPUT, it's not supported on old sway releases.
        common.i3.on(Event.WORKSPACE, on_i3ipc_event)
        common.i3.on(Event.WINDOW, on_i3ipc_event)

        # We monitor i3ipc events in a separate thread, and callbacks will also
        # be executed there. Hence, UI operations MUST be scheduled by
        # Gdk.threads_add_*() or their GLib counterpart to make them happen in
        # Gtk's main loop.
        thread = threading.Thread(target=common.i3.main, daemon=True)
        thread.start()

    if his:
        if len(common.h_taskbars_list) > 0 or len(common.h_workspaces_list) > 0:
            print("his: '{}', starting hypr_watcher".format(his))
            # read from Hyprland socket2 on another thread
            thread = threading.Thread(target=hypr_watcher)
            thread.daemon = True
            thread.start()

    if tray_available and len(common.tray_list) > 0:
        sni_system_tray.init_tray(common.tray_list)

    Gtk.main()


if __name__ == "__main__":
    sys.exit(main())
