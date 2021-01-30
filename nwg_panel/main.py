#!/usr/bin/python3

import sys
import signal
import gi
import argparse

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

from tools import *

from modules.custom_button import CustomButton
from modules.executor import Executor
from modules.clock import Clock
from modules.controls import Controls
from modules.playerctl import Playerctl
from modules.cpu_avg import CpuAvg

common.sway = os.getenv('SWAYSOCK') is not None
if common.sway:
    from i3ipc import Connection

    common.i3 = Connection()
    from modules.sway_taskbar import SwayTaskbar
    from modules.sway_workspaces import SwayWorkspaces

try:
    from pyalsa import alsamixer

    common.dependencies["pyalsa"] = True
except:
    print("pylsa module not found, will try amixer")

restart_cmd = ""


def signal_handler(sig, frame):
    print("SIGINT received, terminating")
    Gtk.main_quit()


def restart():
    subprocess.Popen(restart_cmd, shell=True)


def check_tree():
    old = len(common.outputs)
    common.outputs = list_outputs(silent=True)
    new = len(common.outputs)
    if old != 0 and old != new:
        print("Number of outputs changed")
        restart()

    # Do if tree changed
    tree = common.i3.get_tree()
    if tree.ipc_data != common.ipc_data:
        for item in common.taskbars_list:
            item.refresh()

        for item in common.controls_list:
            if item.popup_window.get_visible():
                item.popup_window.hide()

    common.ipc_data = common.i3.get_tree().ipc_data

    return True


def instantiate_content(panel, container, content_list):
    check_key(panel, "items-padding", 0)
    check_key(panel, "icons", "")
    if panel["icons"] == "light":
        common.icons_path = "icons_light"
    elif panel["icons"] == "dark":
        common.icons_path = "icons_dark"

    check_key(panel, "position", "top")
    for item in content_list:
        if item == "sway-taskbar":
            if "sway-taskbar" in panel:
                if common.sway:
                    check_key(panel["sway-taskbar"], "all-outputs", False)
                    if panel["sway-taskbar"]["all-outputs"] or "output" not in panel:
                        taskbar = SwayTaskbar(panel["sway-taskbar"], common.i3, panel["position"])
                    else:
                        taskbar = SwayTaskbar(panel["sway-taskbar"], common.i3, panel["position"],
                                              display_name="{}".format(panel["output"]))
                    common.taskbars_list.append(taskbar)

                    container.pack_start(taskbar, False, False, panel["items-padding"])
                else:
                    print("'sway-taskbar' ignored")
            else:
                print("'sway-taskbar' not defined in this panel instance")

        if item == "sway-workspaces":
            if common.sway:
                if "sway-workspaces" in panel:
                    workspaces = SwayWorkspaces(panel["sway-workspaces"])
                    container.pack_start(workspaces, False, False, panel["items-padding"])
                else:
                    print("'sway-workspaces' not defined in this panel instance")
            else:
                print("'sway-workspaces' ignored")
        if "button-" in item:
            if item in panel:
                button = CustomButton(panel[item])
                container.pack_start(button, False, False, panel["items-padding"])
            else:
                print("'{}' not defined in this panel instance".format(item))

        if "executor-" in item:
            if item in panel:
                executor = Executor(panel[item])
                container.pack_start(executor, False, False, panel["items-padding"])
            else:
                print("'{}' not defined in this panel instance".format(item))

        if item == "clock":
            if item in panel:
                clock = Clock(panel[item])
                container.pack_start(clock, False, False, panel["items-padding"])
            else:
                clock = Clock({})
                container.pack_start(clock, False, False, panel["items-padding"])

        if item == "playerctl":
            if item in panel:
                playerctl = Playerctl(panel[item])
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

    args = parser.parse_args()
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

    common.app_dirs = get_app_dirs()

    common.dependencies["upower"] = is_command("upower")
    common.dependencies["acpi"] = is_command("acpi")

    config_file = os.path.join(common.config_dir, args.config)

    common.outputs = list_outputs()

    panels = load_json(config_file)

    screen = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    style_context = Gtk.StyleContext()
    style_context.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    try:
        provider.load_from_path(os.path.join(common.config_dir, args.style))
    except Exception as e:
        print(e)

    for panel in panels:
        if panel["output"] in common.outputs:
            check_key(panel, "spacing", 6)
            check_key(panel, "homogeneous", False)
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
            # If not full screen width demanded explicit, let's leave 6 pixel of margin on both sides on multi-headed
            # setups. Otherwise moving the pointer between displays over the panels remains undetected,
            # and the Controls window may appear on the previous output.
            if "output" in panel and panel["output"] and "width" not in panel:
                panel["width"] = common.outputs[panel["output"]]["width"]

            check_key(panel, "width", 0)
            w = panel["width"]
            check_key(panel, "height", 0)
            h = panel["height"]

            check_key(panel, "controls", False)
            if panel["controls"]:
                check_key(panel, "controls-settings", {})

            if "controls-settings" in panel:
                controls_settings = panel["controls-settings"]
                check_key(controls_settings, "alignment", "right")
                check_key(controls_settings, "show-values", False)

            Gtk.Widget.set_size_request(window, w, h)

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            vbox.pack_start(hbox, True, True, panel["padding-vertical"])

            inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            if panel["homogeneous"]:
                inner_box.set_homogeneous(True)
            hbox.pack_start(inner_box, True, True, panel["padding-horizontal"])

            left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=panel["spacing"])
            inner_box.pack_start(left_box, False, True, 0)
            if panel["controls"] and panel["controls-settings"]["alignment"] == "left":
                monitor = None
                try:
                    monitor = common.outputs[panel["output"]]["monitor"]
                except KeyError:
                    pass

                cc = Controls(panel["controls-settings"], panel["position"], panel["controls-settings"]["alignment"],
                              int(w / 6), monitor=monitor)
                common.controls_list.append(cc)
                left_box.pack_start(cc, False, False, 0)
            check_key(panel, "modules-left", [])
            instantiate_content(panel, left_box, panel["modules-left"])

            center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=panel["spacing"])
            inner_box.pack_start(center_box, True, False, 0)
            check_key(panel, "modules-center", [])
            instantiate_content(panel, center_box, panel["modules-center"])

            right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=panel["spacing"])
            # Damn on the guy who invented `pack_start(child, expand, fill, padding)`!
            helper_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            helper_box.pack_end(right_box, False, False, 0)
            inner_box.pack_start(helper_box, False, True, 0)
            check_key(panel, "modules-right", [])
            instantiate_content(panel, right_box, panel["modules-right"])

            if panel["controls"] and panel["controls-settings"]["alignment"] == "right":
                monitor = None
                try:
                    monitor = common.outputs[panel["output"]]["monitor"]
                except KeyError:
                    pass

                cc = Controls(panel["controls-settings"], panel["position"], panel["controls-settings"]["alignment"],
                              int(w / 6), monitor=monitor)
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
            print("Display: {}, position: {}, layer: {}, width: {}, height: {}".format(o, panel["position"],
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
            # window.connect('destroy', Gtk.main_quit)

    if common.key_missing:
        print("Saving amended config")
        save_json(panels, os.path.join(common.config_dir, "config_amended"))

    # GLib.timeout_add(100, listener_reply)
    if common.sway:
        Gdk.threads_add_timeout(GLib.PRIORITY_DEFAULT_IDLE, 150, check_tree)

    signal.signal(signal.SIGINT, signal_handler)

    Gtk.main()


if __name__ == "__main__":
    sys.exit(main())
