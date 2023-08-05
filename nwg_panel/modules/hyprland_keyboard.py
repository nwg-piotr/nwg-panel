#!/usr/bin/env python3

from gi.repository import Gtk, Gdk

from nwg_panel.tools import check_key, update_image_fallback_desktop, hyprctl


class HyprlandKeyboard(Gtk.Box):
    def __init__(self, settings, devices):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.settings = settings
        self.label = Gtk.Label()

        self.build_box()
        self.refresh(devices)

    def build_box(self):
        check_key(self.settings, "angle", 0.0)
        check_key(self.settings, "device", None)

        if self.settings["angle"] != 0.0:
            self.set_orientation(Gtk.Orientation.VERTICAL)
            self.num_box.set_orientation(Gtk.Orientation.VERTICAL)

        self.pack_start(self.label, False, False, 0)

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
        

    def on_click(self, event_box, event_button, num):
        hyprctl("dispatch switchxkblayout next")

    def on_scroll(self, event_box, event):
        pass

    def on_enter_notify_event(self, widget, event):
        widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
        widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)

    def on_leave_notify_event(self, widget, event):
        widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
        widget.unset_state_flags(Gtk.StateFlags.SELECTED)
