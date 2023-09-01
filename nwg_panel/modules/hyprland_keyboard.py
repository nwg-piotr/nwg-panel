#!/usr/bin/env python3

from gi.repository import Gtk, Gdk

from nwg_panel.tools import check_key, update_image_fallback_desktop, hyprctl


class HyprlandKeyboard(Gtk.EventBox):
    def __init__(self, settings, devices):
        Gtk.EventBox.__init__(self)

        self.label = Gtk.Label.new("default")
        self.add(self.label)

        self.settings = settings
        defaults = {
            "device": "",
            "css-name": ""
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        self.refresh(devices)
        self.connect("button-release-event", self.on_click)
        self.add_events(Gdk.EventMask.SCROLL_MASK)
        self.connect("scroll-event", self.on_scroll)

        if self.settings["css-name"]:
            self.set_property("name",self.settings["css-name"])
        else:
            self.set_property("name","executor-label")
        self.show_all()

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
        self.label.set_text(layout)

    def on_click(self, event_box, button):
        hyprctl("switchxkblayout {} next".format(self.settings["device"]))

    def on_scroll(self, button, event):
        if event.direction == Gdk.ScrollDirection.UP:
            hyprctl("switchxkblayout {} prev".format(self.settings["device"]))
        elif event.direction == Gdk.ScrollDirection.DOWN:
            hyprctl("switchxkblayout {} next".format(self.settings["device"]))
