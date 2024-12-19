#!/usr/bin/env python3

import json
import subprocess

from gi.repository import Gtk, GLib
from i3ipc import Event

from nwg_panel.tools import check_key, update_image


class SwayMode(Gtk.Box):
    def __init__(self, i3, settings, icons_path=""):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.settings = settings
        self.i3 = i3
        self.label = Gtk.Label.new("default")
        self.mode = "default"

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

        self.check_initial_mode()

        if self.mode == "default" and not self.settings["show-default"]:
            GLib.idle_add(self.hide, priority=GLib.PRIORITY_HIGH)

        self.i3.on(Event.MODE, self.on_i3ipc_event)

    def check_initial_mode(self):
        # On panel startup we may already be in some mode other than default,
        # but we only check it on i3ipc event.
        # As i3ipc seemingly does not implement the `get_binding_state` function,
        # for initial check we need to parse `swaymsg -t get_binding_state` output.
        self.mode = "default"
        o = subprocess.check_output("swaymsg -t get_binding_state".split()).decode("utf-8")
        try:
            self.mode = json.loads(o)["name"]
        except KeyError:
            pass
        self.set_visibility()

    def on_i3ipc_event(self, i3conn, event):
        self.mode = event.change
        self.set_visibility()

    def set_visibility(self):
        self.label.set_text(self.mode)
        if self.mode != "default" or self.settings["show-default"]:
            self.show_all()
        else:
            self.hide()
