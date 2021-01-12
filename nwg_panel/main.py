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

from gi.repository import Gtk, GtkLayerShell, GLib

from i3ipc import Connection


i3 = Connection()

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5555")


def i3ipc_reply():
    message = socket.recv()
    print("Received request: %s" % message)

    check_tree(i3)

    #  Send reply back to client
    socket.send(b"World")
    return True


def main():

    window = Gtk.Window()
    common.test_label = Gtk.Label(label='GTK Layer Shell with Python!')
    window.add(common.test_label)

    GtkLayerShell.init_for_window(window)
    GtkLayerShell.auto_exclusive_zone_enable(window)
    GtkLayerShell.set_margin(window, GtkLayerShell.Edge.TOP, 0)
    GtkLayerShell.set_margin(window, GtkLayerShell.Edge.BOTTOM, 0)
    GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.BOTTOM, 1)

    window.show_all()
    window.connect('destroy', Gtk.main_quit)

    GLib.timeout_add(50, i3ipc_reply)
    Gtk.main()


if __name__ == "__main__":
    sys.exit(main())