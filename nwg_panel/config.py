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


class PanelSelector(Gtk.Window):
    def __init__(self, parent):
        super(PanelSelector, self).__init__()
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_keep_above(True)
        self.connect("key-release-event", handle_keyboard)
        self.connect('destroy', self.release_parent, parent)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        vbox.pack_start(hbox, True, True, 20)

        self.add(vbox)

        grid = Gtk.Grid()
        grid.set_column_spacing(20)
        grid.set_row_spacing(4)

        hbox.pack_start(grid, True, True, 20)

        row = 0
        for path in configs:
            label = Gtk.Label()
            label.set_text("File: {}".format(path))
            label.set_halign(Gtk.Align.START)
            grid.attach(label, 0, row, 3, 1)
            row += 1

            panels = configs[path]

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

            panel_idx = 0
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

                button = Gtk.Button.new_from_icon_name("document-edit", Gtk.IconSize.BUTTON)
                button.set_label("edit")
                button.connect("clicked", self.on_button_clicked, path, panel_idx)
                grid.attach(button, 3, row, 1, 1)

                row += 1
                panel_idx += 1

        self.show_all()
    
    def on_button_clicked(self, button, file, panel):
        print("Panel {} in {}".format(panel, file))
        
    def release_parent(self, w, parent):
        parent.set_sensitive(True)


def main():
    global configs
    configs = list_configs(config_dir)

    GLib.set_prgname('nwg-panel-config')

    builder = Gtk.Builder()
    builder.add_from_file("glade/panel_edit.glade")
    
    window = builder.get_object("panel_edit_win")
    window.show_all()
    window.connect('destroy', Gtk.main_quit)
    window.connect("key-release-event", handle_keyboard)
    window.set_sensitive(False)

    selector = PanelSelector(window)

    Gtk.main()


if __name__ == "__main__":
    sys.exit(main())
