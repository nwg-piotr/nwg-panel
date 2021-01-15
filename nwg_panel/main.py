#!/usr/bin/python3

import sys
import zmq

import common
from tools import *

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

# from i3ipc import Connection

from modules.sway_taskbar import SwayTaskbar

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5555")


def listener_reply():
    for item in common.panels_list:
        item.refresh()

    return True


def instantiate_content(panel, container, content_list):
    for item in content_list:
        if item == "sway-taskbar":
            taskbar = SwayTaskbar(panel["sway-taskbar"], display_name="{}".format(panel["output"]), spacing=16)
            common.panels_list.append(taskbar)

            container.pack_start(taskbar, False, False, 6)


def main():

    common.config_dir = get_config_dir()
    config_file = os.path.join(common.config_dir, "config")

    panels = load_json(config_file)

    screen = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    style_context = Gtk.StyleContext()
    style_context.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    try:
        provider.load_from_path(os.path.join(common.config_dir, "style.css"))
    except Exception as e:
        print(e)

    for panel in panels:
        common.i3.command("focus output {}".format(panel["output"]))
        window = Gtk.Window()
        Gtk.Widget.set_size_request(window, 1920, 20)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        vbox.pack_start(hbox, True, True, 2)

        inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        hbox.pack_start(inner_box, True, True, 0)
        
        left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        inner_box.pack_start(left_box, True, True, 0)
        instantiate_content(panel, left_box, panel["modules-left"])

        center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        inner_box.pack_start(center_box, True, True, 0)
        instantiate_content(panel, center_box, panel["modules-center"])

        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        inner_box.pack_end(right_box, True, True, 0)
        instantiate_content(panel, right_box, panel["modules-right"])

        """taskbar = SwayTaskbar(display_name="{}".format(panel["output"]), spacing=16)
        common.panels_list.append(taskbar)
        
        hbox.pack_start(taskbar, False, False, 6)"""

        window.add(vbox)

        GtkLayerShell.init_for_window(window)
        GtkLayerShell.auto_exclusive_zone_enable(window)
        GtkLayerShell.set_margin(window, GtkLayerShell.Edge.TOP, 2)
        GtkLayerShell.set_margin(window, GtkLayerShell.Edge.BOTTOM, 2)
        GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.BOTTOM, 1)

        window.show_all()
        window.connect('destroy', Gtk.main_quit)

    GLib.timeout_add(100, listener_reply)
    Gtk.main()


if __name__ == "__main__":
    sys.exit(main())