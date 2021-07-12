#!/usr/bin/python3

import sys
import signal
import gi
import argparse

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

from nwg_panel.modules.menu_start import MenuStart

dir_name = os.path.dirname(__file__)

from nwg_panel import common

sway = os.getenv('SWAYSOCK') is not None
if sway:
    try:
        from i3ipc import Connection
    except ModuleNotFoundError:
        print("'python-i3ipc' package required on sway, terminating")
        sys.exit(1)

    common.i3 = Connection()
    from nwg_panel.modules.sway_taskbar import SwayTaskbar
    from nwg_panel.modules.sway_workspaces import SwayWorkspaces

restart_cmd = ""


def signal_handler(sig, frame):
    desc = {2: "SIGINT", 15: "SIGTERM"}
    print("Terminated with {}".format(desc[sig]))
    Gtk.main_quit()


def restart():
    subprocess.Popen(restart_cmd, shell=True)


def check_tree():
    tree = common.i3.get_tree() if sway else None
    if tree:
        # Do if tree changed
        if tree.ipc_data != common.ipc_data:
            if len(common.i3.get_outputs()) != common.outputs_num:
                print("Number of outputs changed")
                restart()

            for item in common.taskbars_list:
                item.refresh(tree)

            for item in common.scratchpads_list:
                item.refresh(tree)

            for item in common.workspaces_list:
                item.refresh()

            for item in common.controls_list:
                if item.popup_window.get_visible():
                    item.popup_window.hide()

        common.ipc_data = tree.ipc_data

    else:
        pass
        """ For now we seem to have no reason to trace it outside sway
        old = len(common.outputs)
        common.outputs = list_outputs(sway=sway, tree=tree, silent=True)
        new = len(common.outputs)
        if old != 0 and old != new:
            print("Number of outputs changed")
            restart()"""

    return True


def instantiate_content(panel, container, content_list, icons_path=""):
    check_key(panel, "position", "top")
    check_key(panel, "items-padding", 0)
    for item in content_list:
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
                    common.taskbars_list.append(taskbar)

                    container.pack_start(taskbar, False, False, panel["items-padding"])
                else:
                    print("'sway-taskbar' ignored")
            else:
                print("'sway-taskbar' not defined in this panel instance")

        if item == "sway-workspaces":
            if sway:
                if "sway-workspaces" in panel:
                    workspaces = SwayWorkspaces(panel["sway-workspaces"], common.i3, icons_path=icons_path)
                    container.pack_start(workspaces, False, False, panel["items-padding"])
                    common.workspaces_list.append(workspaces)
                else:
                    print("'sway-workspaces' not defined in this panel instance")
            else:
                print("'sway-workspaces' ignored")

        if item == "scratchpad":
            if sway:
                # Added in v0.1.3, so may be undefined in user's config.
                if item not in panel:
                    panel["scratchpad"] = {}
                scratchpad = Scratchpad(common.i3, common.i3.get_tree(), panel[item])
                container.pack_start(scratchpad, False, False, panel["items-padding"])
                common.scratchpads_list.append(scratchpad)
            else:
                print("'scratchpad' ignored")

        if "button-" in item:
            if item in panel:
                button = CustomButton(panel[item], icons_path)
                container.pack_start(button, False, False, panel["items-padding"])
            else:
                print("'{}' not defined in this panel instance".format(item))

        if "executor-" in item:
            if item in panel:
                executor = Executor(panel[item], icons_path)
                container.pack_start(executor, False, False, panel["items-padding"])
            else:
                print("'{}' not defined in this panel instance".format(item))

        if item == "clock":
            if item in panel:
                clock = Clock(panel[item])
                container.pack_start(clock, False, False, panel["items-padding"])
            else:
                clock = Clock({})
                container.pack_start(clock, False, False, 0)

        if item == "playerctl":
            if item in panel:
                playerctl = Playerctl(panel[item], icons_path)
                container.pack_start(playerctl, False, False, panel["items-padding"])
            else:
                print("'{}' not defined in this panel instance".format(item))

        if item == "cpu-avg":
            cpu_avg = CpuAvg()
            container.pack_start(cpu_avg, False, False, panel["items-padding"])


def main():
    common.config_dir = get_config_dir()

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

    parser.add_argument("-r",
                        "--restore",
                        action="store_true",
                        help="restore default config files")

    parser.add_argument("-v",
                        "--version",
                        action="version",
                        version="%(prog)s {}".format(__version__),
                        help="display version information")

    args = parser.parse_args()

    check_commands()
    print("Dependencies check:", common.commands)

    global restart_cmd
    restart_cmd = "nwg-panel -c {} -s {}".format(args.config, args.style)

    # Try and kill already running instance if any
    pid_file = os.path.join(temp_dir(), "nwg-panel.pid")
    if os.path.isfile(pid_file):
        try:
            pid = int(load_text_file(pid_file))
            os.kill(pid, signal.SIGINT)
            print("Running instance killed, PID {}".format(pid))
        except:
            pass
    save_string(str(os.getpid()), pid_file)

    save_string("-c {} -s {}".format(args.config, args.style), os.path.join(local_dir(), "args"))

    common.app_dirs = get_app_dirs()

    config_file = os.path.join(common.config_dir, args.config)

    copy_files(os.path.join(dir_name, "icons_light"), os.path.join(common.config_dir, "icons_light"))
    copy_files(os.path.join(dir_name, "icons_dark"), os.path.join(common.config_dir, "icons_dark"))
    copy_executors(os.path.join(dir_name, "executors"), os.path.join(common.config_dir, "executors"))
    copy_files(os.path.join(dir_name, "config"), common.config_dir, args.restore)

    tree = common.i3.get_tree() if sway else None
    common.outputs = list_outputs(sway=sway, tree=tree)

    panels = load_json(config_file)

    screen = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    style_context = Gtk.StyleContext()
    style_context.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    try:
        provider.load_from_path(os.path.join(common.config_dir, args.style))
    except Exception as e:
        print(e)

    # Mirror bars to all outputs #48 (if panel["output"] == "All")
    to_remove = []
    to_append = []
    for panel in panels:
        check_key(panel, "output", "")

        clones = []
        if panel["output"] == "All" and len(common.outputs) > 1:
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
            window = Gtk.Window()
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
                    "terminal": "alacritty",
                    "width": 0
                }
                for key in defaults:
                    check_key(panel["menu-start-settings"], key, defaults[key])
            
            if panel["menu-start"] != "off":
                panel["menu-start-settings"]["horizontal-align"] = panel["menu-start"]

            Gtk.Widget.set_size_request(window, w, h)

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            vbox.pack_start(hbox, True, True, panel["padding-vertical"])

            check_key(panel, "modules-left", [])
            check_key(panel, "modules-center", [])
            check_key(panel, "modules-right", [])

            # This is to allow the "auto" value. Actually all non-numeric values will be removed.
            if "homogeneous" in panel and not isinstance(panel["homogeneous"], bool):
                panel.pop("homogeneous")

            # set equal columns width by default if "modules-center" not empty; this may be overridden in config
            if panel["modules-center"]:
                check_key(panel, "homogeneous", True)
            else:
                check_key(panel, "homogeneous", False)

            inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            inner_box.set_homogeneous(panel["homogeneous"])

            hbox.pack_start(inner_box, True, True, panel["padding-horizontal"])

            left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=panel["spacing"])
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

            if panel["menu-start"] == "left":
                ms = MenuStart(panel, icons_path=icons_path)
                left_box.pack_start(ms, False, False, 0)

            instantiate_content(panel, left_box, panel["modules-left"], icons_path=icons_path)

            center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=panel["spacing"])
            inner_box.pack_start(center_box, True, False, 0)
            check_key(panel, "modules-center", [])
            instantiate_content(panel, center_box, panel["modules-center"], icons_path=icons_path)

            right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=panel["spacing"])
            # Damn on the guy who invented `pack_start(child, expand, fill, padding)`!
            helper_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            helper_box.pack_end(right_box, False, False, 0)
            inner_box.pack_start(helper_box, False, True, 0)
            check_key(panel, "modules-right", [])
            instantiate_content(panel, right_box, panel["modules-right"], icons_path=icons_path)

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

            window.add(vbox)

            GtkLayerShell.init_for_window(window)

            monitor = None
            try:
                monitor = common.outputs[panel["output"]]["monitor"]
            except KeyError:
                pass

            check_key(panel, "layer", "top")
            o = panel["output"] if "output" in panel else "undefined"
            print("Output: {}, position: {}, layer: {}, width: {}, height: {}".format(o, panel["position"],
                                                                                      panel["layer"], panel["width"],
                                                                                      panel["height"]))

            if monitor:
                GtkLayerShell.set_monitor(window, monitor)

            GtkLayerShell.auto_exclusive_zone_enable(window)

            if panel["layer"] == "top":
                GtkLayerShell.set_layer(window, GtkLayerShell.Layer.TOP)
            else:
                GtkLayerShell.set_layer(window, GtkLayerShell.Layer.BOTTOM)

            check_key(panel, "margin-top", 0)
            GtkLayerShell.set_margin(window, GtkLayerShell.Edge.TOP, panel["margin-top"])

            check_key(panel, "margin-bottom", 0)
            GtkLayerShell.set_margin(window, GtkLayerShell.Edge.BOTTOM, panel["margin-bottom"])

            if panel["position"] == "top":
                GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.TOP, 1)
            else:
                GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.BOTTOM, 1)

            window.show_all()

    if sway:
        common.outputs_num = len(common.i3.get_outputs())
    else:
        common.outputs = list_outputs(sway=sway, tree=tree, silent=True)
        common.outputs_num = len(common.outputs)
    Gdk.threads_add_timeout(GLib.PRIORITY_DEFAULT_IDLE, 20, check_tree)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    Gtk.main()


if __name__ == "__main__":
    sys.exit(main())
