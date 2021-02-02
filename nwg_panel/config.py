#!/usr/bin/python3

import os
import sys
import json

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

from nwg_panel.tools import get_config_dir, load_json, list_outputs, check_key, is_command, list_configs

config_dir = get_config_dir()
configs = {}


def handle_keyboard(window, event):
    if event.type == Gdk.EventType.KEY_RELEASE and event.keyval == Gdk.KEY_Escape:
        window.close()


def main():
    global configs
    configs = list_configs(config_dir)

    GLib.set_prgname('nwg-panel-config')

    window = Gtk.Window()
    window.connect("key-release-event", handle_keyboard)

    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    vbox.pack_start(hbox, True, True, 20)

    window.add(vbox)

    grid = Gtk.Grid()
    grid.set_column_spacing(20)
    grid.set_row_spacing(4)

    hbox.pack_start(grid, True, True, 20)
            
    row = 0
    for key in configs:
        label = Gtk.Label()
        label.set_text("File: {}".format(key))
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 3, 1)

        button = Gtk.Button.new_from_icon_name("document-edit", Gtk.IconSize.BUTTON)
        button.set_label("edit")
        grid.attach(button, 4, row, 1, 1)
        row += 1
        
        panels = configs[key]

        label = Gtk.Label()
        label.set_text("PANEL NAME")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 1, 1)

        label = Gtk.Label()
        label.set_text("OUTPUT")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 1, row, 1, 1)

        label = Gtk.Label()
        label.set_text("POSITION")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 2, row, 1, 1)

        row += 1
        for panel in panels:
            check_key(panel, "name", "-")
            check_key(panel, "output", "-")
            check_key(panel, "position", "-")

            label = Gtk.Label()
            label.set_text(panel["name"])
            label.set_halign(Gtk.Align.START)
            grid.attach(label, 0, row, 1, 1)

            label = Gtk.Label()
            label.set_text(panel["output"])
            label.set_halign(Gtk.Align.START)
            grid.attach(label, 1, row, 1, 1)

            label = Gtk.Label()
            label.set_text(panel["position"])
            label.set_halign(Gtk.Align.START)
            grid.attach(label, 2, row, 1, 1)

            row += 1

    window.show_all()
    window.connect('destroy', Gtk.main_quit)
    
    Gtk.main()


if __name__ == "__main__":
    sys.exit(main())
