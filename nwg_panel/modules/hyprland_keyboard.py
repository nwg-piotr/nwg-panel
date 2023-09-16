#!/usr/bin/env python3

from gi.repository import Gtk, Gdk

from nwg_panel.tools import check_key, update_image_fallback_desktop, hyprctl, lookup_layout, eprint


class HyprlandKeyboard(Gtk.EventBox):
    def __init__(self, settings, devices):
        Gtk.EventBox.__init__(self)

        self.label = Gtk.Label.new("default")
        self.add(self.label)

        self.settings = settings
        defaults = {
            "format": "{short}",
            "device": "",
            "css-name": "",
            "angle": 0.0
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        self.refresh(devices)
        self.connect("button-release-event", self.on_click)
        self.add_events(Gdk.EventMask.SCROLL_MASK)
        self.connect("scroll-event", self.on_scroll)

        if settings["angle"] != 0.0:
            #self.set_orientation(Gtk.Orientation.VERTICAL)
            self.label.set_angle(settings["angle"])

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
        kb = self.get_main_kb()
        return kb["active_keymap"]

    def get_main_kb(self):
        for kb in self.devices["keyboards"]:
            if kb["main"]:
                return kb

    def change_layout(self, direction):
        status = hyprctl("switchxkblayout {kb} {direction}".format(kb = self.settings["device"], direction = direction))
        if status != "ok":
            hyprctl("switchxkblayout {kb} {direction}".format(kb = self.get_main_kb()["name"], direction = direction))

    def refresh(self, devices):
        self.devices = devices
        layout_description = self.get_active_keymap(devices)
        layout_dict = lookup_layout(layout_description)
        try:
            text = self.settings["format"].format(**layout_dict)
        except:
            text = ""
            eprint("Invalid Hyprland-keyboard format.")
            
            
        self.label.set_text(text)

    def on_click(self, event_box, button):
        self.change_layout("next")

    def on_scroll(self, button, event):
        if event.direction == Gdk.ScrollDirection.UP:
            self.change_layout("prev")
        elif event.direction == Gdk.ScrollDirection.DOWN:
            self.change_layout("next")
