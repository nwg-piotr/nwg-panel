#!/usr/bin/env python3

from gi.repository import Gtk, GLib
from i3ipc import Event

from nwg_panel.tools import check_key, update_image


class SwayMode(Gtk.Box):
    def __init__(self, i3, settings, icons_path=""):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.settings = settings
        self.i3 = i3
        self.label = Gtk.Label.new("default")

        icon = Gtk.Image()

        defaults = {
            "show-default": False,
            "show-icon": True,
            "css-name": "",
            "icon-size": 16,
            "angle": 0.0
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        update_image(icon, "mode", self.settings["icon-size"], icons_path)

        if self.settings["css-name"]:
            self.set_property("name", self.settings["css-name"])
        else:
            self.set_property("name", "executor-label")

        if settings["angle"] != 0.0:
            self.set_orientation(Gtk.Orientation.VERTICAL)
            self.label.set_angle(settings["angle"])

        if settings["show-icon"]:
            self.pack_start(icon, False, False, 2)

        self.pack_start(self.label, False, False, 2)

        if not self.settings["show-default"]:
            GLib.idle_add(self.hide, priority=GLib.PRIORITY_HIGH)

        self.i3.on(Event.MODE, self.on_i3ipc_event)

    def on_i3ipc_event(self, i3conn, event):
        mode = event.change
        self.label.set_text(mode)
        if mode != "default" or self.settings["show-default"]:
            self.show_all()
        else:
            self.hide()
