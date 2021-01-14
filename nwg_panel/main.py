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

from i3ipc import Connection

from modules.workspaces import SwayWorkspaces


i3 = Connection()

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5555")


def listener_reply():
    message = socket.recv()
    print("Received request: %s" % message)

    check_tree(i3)

    #  Send reply back to client
    socket.send(b"World")
    return True


def main():
    
    """display = Gdk.Display().get_default()
    for d in range(display.get_n_monitors()):
        monitor = display.get_monitor(d)
        geometry = monitor.get_geometry()
        print(monitor.get_display().get_name(), geometry.x, geometry.y, geometry.width, geometry.height)"""

    common.config_dir = get_config_dir()
    config_file = os.path.join(common.config_dir, "config")
    config = sample_config()
    save_json(config, config_file)

    window = Gtk.Window()
    Gtk.Widget.set_size_request(window, 1920, 20)

    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    vbox.pack_start(hbox, True, True, 2)

    sws = SwayWorkspaces(display_name="eDP-1", spacing=16)
    hbox.pack_start(sws, False, False, 6)

    """b = Gtk.Button(label="Test")
    hbox.pack_start(b, False, False, 10)
    common.test_label = Gtk.Label(label='         GTK Layer Shell with Python!              ')
    hbox.pack_start(common.test_label, False, False, 0)"""
    window.add(vbox)

    GtkLayerShell.init_for_window(window)
    GtkLayerShell.auto_exclusive_zone_enable(window)
    GtkLayerShell.set_margin(window, GtkLayerShell.Edge.TOP, 2)
    GtkLayerShell.set_margin(window, GtkLayerShell.Edge.BOTTOM, 2)
    GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.TOP, 1)

    window.show_all()
    window.connect('destroy', Gtk.main_quit)

    GLib.timeout_add(50, listener_reply)
    Gtk.main()


if __name__ == "__main__":
    sys.exit(main())