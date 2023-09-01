#!/usr/bin/env python3

from gi.repository import Gtk, Gdk

from nwg_panel.tools import check_key, update_image_fallback_desktop, hyprctl


class HyprlandKeyboard(Gtk.Button):
    def __init__(self, settings, devices):
        Gtk.Button.__init__(self)
        self.settings = settings

        self.refresh(devices)
        self.connect("clicked", self.on_click)
        self.show()

    def get_active_keymap(self, devices):
        if self.settings["device"]:
            for kb in devices["keyboards"]:
                if kb["name"] == self.settings["device"]:
                    return kb["active_keymap"]

        for kb in devices["keyboards"]:
            if kb["main"]:
                return kb["active_keymap"]

    def refresh(self, devices):
        layout = self.get_active_keymap(devices)
        self.set_label(layout)
        

    def on_click(self, button):
        hyprctl("switchxkblayout {} next".format(self.settings["device"]))
