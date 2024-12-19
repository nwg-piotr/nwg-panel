#!/usr/bin/env python3

from gi.repository import Gtk, GLib

from nwg_panel.tools import check_key, update_image, hyprctl


class HyprlandSubmap(Gtk.Box):
    def __init__(self, settings, icons_path=""):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.settings = settings
        self.label = Gtk.Label.new("default")
        self.submap = "default"

        icon = Gtk.Image()

        defaults = {
            "show-default": False,
            "show-icon": True,
            "css-name": "executor-label",
            "icon-size": 16,
            "angle": 0.0
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        update_image(icon, "object-flip-vertical", self.settings["icon-size"], icons_path)

        if self.settings["css-name"]:
            self.set_property("name", self.settings["css-name"])
        else:
            self.set_property("name", "executor-label")

        if settings["angle"] != 0.0:
            self.set_orientation(Gtk.Orientation.VERTICAL)
            self.label.set_angle(settings["angle"])

        if settings["show-icon"]:
            self.pack_start(icon, False, False, 0)

        self.pack_start(self.label, False, False, 6)

        self.refresh()

        if self.submap == "default" and not self.settings["show-default"]:
            GLib.idle_add(self.hide, priority=GLib.PRIORITY_HIGH)

    def refresh(self):
        self.submap = hyprctl("submap").strip()
        self.label.set_text(self.submap)
        if self.submap != "default" or self.settings["show-default"]:
            self.show_all()
        else:
            self.hide()
