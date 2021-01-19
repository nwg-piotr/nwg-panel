#!/usr/bin/python3

import sys
import gi

gi.require_version('Gtk', '3.0')
try:
    gi.require_version('GtkLayerShell', '0.1')
except ValueError:

    raise RuntimeError('\n\n' +
                       'If you haven\'t installed GTK Layer Shell, you need to point Python to the\n' +
                       'library by setting GI_TYPELIB_PATH and LD_LIBRARY_PATH to <build-dir>/src/.\n' +
                       'For example you might need to run:\n\n' +
                       'GI_TYPELIB_PATH=build/src LD_LIBRARY_PATH=build/src python3 ' + ' '.join(sys.argv))

from gi.repository import Gtk, GtkLayerShell, GLib, Gdk

from tools import *
from modules.sway_taskbar import SwayTaskbar
from modules.sway_workspaces import SwayWorkspaces
from modules.custom_button import CustomButton
from modules.executor import Executor


def listener_reply():
    for item in common.taskbars_list:
        item.refresh()

    return True


def instantiate_content(panel, container, content_list):
    for item in content_list:
        if item == "sway-taskbar":
            if "sway-taskbar" in panel:
                check_key(panel["sway-taskbar"], "all-outputs", False)
                if panel["sway-taskbar"]["all-outputs"]:
                    taskbar = SwayTaskbar(panel["sway-taskbar"])
                else:
                    taskbar = SwayTaskbar(panel["sway-taskbar"], display_name="{}".format(panel["output"]))
                common.taskbars_list.append(taskbar)
    
                container.pack_start(taskbar, True, False, 0)
            else:
                print("'sway-taskbar' not defined in this panel instance")
            
        if item == "sway-workspaces":
            if "sway-workspaces" in panel:
                workspaces = SwayWorkspaces(panel["sway-workspaces"])
                container.pack_start(workspaces, True, False, 0)
            else:
                print("'sway-workspaces' not defined in this panel instance")
                
        if "button-" in item:
            if item in panel:
                button = CustomButton(panel[item])
                container.pack_start(button, True, False, 0)
            else:
                print("'{}' not defined in this panel instance".format(item))
                
        if "executor-" in item:
            if item in panel:
                executor = Executor(panel[item])
                container.pack_start(executor, True, False, 0)
            else:
                print("'{}' not defined in this panel instance".format(item))


def main():
    save_string(str(os.getpid()), os.path.join(temp_dir(), "nwg-panel.pid"))
    
    common.app_dirs = get_app_dirs()

    common.config_dir = get_config_dir()
    config_file = os.path.join(common.config_dir, "config")

    common.outputs = list_outputs()

    panels = load_json(config_file)

    screen = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    style_context = Gtk.StyleContext()
    style_context.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    try:
        provider.load_from_path(os.path.join(common.config_dir, "style.css"))
    except Exception as e:
        print(e)

    output_to_focus = None

    for panel in panels:

        common.i3.command("focus output {}".format(panel["output"]))
        window = Gtk.Window()
        check_key(panel, "width", common.outputs[panel["output"]]["width"])
        w = panel["width"]
        check_key(panel, "height", 0)
        h = panel["height"]

        Gtk.Widget.set_size_request(window, w, h)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        vbox.pack_start(hbox, True, True, panel["padding-vertical"])

        inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        hbox.pack_start(inner_box, True, True, panel["padding-horizontal"])

        check_key(panel, "spacing", 6)
        left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=panel["spacing"])
        inner_box.pack_start(left_box, False, False, 0)
        instantiate_content(panel, left_box, panel["modules-left"])

        center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=panel["spacing"])
        inner_box.pack_start(center_box, True, True, 0)

        instantiate_content(panel, center_box, panel["modules-center"])

        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=panel["spacing"])
        #Gtk.Widget.set_size_request(right_box, third_part, h)
        inner_box.pack_end(right_box, False, False, 0)
        instantiate_content(panel, right_box, panel["modules-right"])

        window.add(vbox)

        GtkLayerShell.init_for_window(window)

        GtkLayerShell.auto_exclusive_zone_enable(window)

        check_key(panel, "layer", "top")
        if panel["layer"] == "top":
            GtkLayerShell.set_layer(window, GtkLayerShell.Layer.TOP)
        else:
            GtkLayerShell.set_layer(window, GtkLayerShell.Layer.BOTTOM)

        check_key(panel, "margin-top", 0)
        GtkLayerShell.set_margin(window, GtkLayerShell.Edge.TOP, panel["margin-top"])

        check_key(panel, "margin-bottom", 0)
        GtkLayerShell.set_margin(window, GtkLayerShell.Edge.BOTTOM, panel["margin-bottom"])

        check_key(panel, "position", "top")
        if panel["position"] == "top":
            GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.TOP, 1)
        else:

            GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.BOTTOM, 1)

        window.show_all()
        window.connect('destroy', Gtk.main_quit)

        """
        As we displace panels by focusing outputs, we always end up in the last output focused on start.
        Let's add the optional "focus" key to the panel placed on the primary output. Whatever non-empty value allowed.
        """
        try:
            if panel["focus"]:
                common.i3.command("focus output {}".format(panel["output"]))
                output_to_focus = panel["output"]
        except KeyError:
            pass

    if output_to_focus:
        common.i3.command("focus output {}".format(output_to_focus))

    #GLib.timeout_add(100, listener_reply)
    Gdk.threads_add_timeout(GLib.PRIORITY_DEFAULT_IDLE, 50, listener_reply)
    Gtk.main()


if __name__ == "__main__":
    sys.exit(main())
