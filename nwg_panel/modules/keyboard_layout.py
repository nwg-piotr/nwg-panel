#!/usr/bin/env python3
import json
import os

import gi

from nwg_panel.tools import check_key, update_image, eprint, hyprctl

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk


def get_kb_layout():
    o = hyprctl("j/getoption input:kb_layout")
    option = json.loads(o)
    if option and "str" in option:
        return option["str"].split(",")
    return []


def list_keyboards():
    o = hyprctl("j/devices")
    devices = json.loads(o)
    keyboards = devices["keyboards"] if "keyboards" in devices else []
    return keyboards


def on_enter_notify_event(widget, event):
    widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
    widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)


def on_leave_notify_event(widget, event):
    widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
    widget.unset_state_flags(Gtk.StateFlags.SELECTED)


class KeyboardLayout(Gtk.EventBox):
    def __init__(self, settings, icons_path):
        self.settings = settings
        self.icons_path = icons_path
        Gtk.EventBox.__init__(self)
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(self.box)
        self.image = Gtk.Image()
        self.label = Gtk.Label.new("")
        self.icon_path = None

        print("KeyboardLayout module")
        if os.getenv("SWAYSOCK"):
            self.compositor = "sway"
        elif os.getenv("HYPRLAND_INSTANCE_SIGNATURE"):
            self.compositor = "hyprland"
        else:
            self.compositor = ""
            eprint("Neither sway nor Hyprland detected, this won't work")

        if self.compositor:
            self.kb_layouts = get_kb_layout()
            print(f"kb_layout = {self.kb_layouts}")

            self.keyboards = list_keyboards()
            self.keyboard_names = []
            for k in self.keyboards:
                self.keyboard_names.append(k["name"])
            print(f"keyboard_names = {self.keyboard_names}")

            check_key(settings, "device-name", "all")
            check_key(settings, "root-css-name", "root-executor")
            check_key(settings, "css-name", "")
            check_key(settings, "icon-placement", "left")
            check_key(settings, "icon-size", 16)
            check_key(settings, "tooltip-text", "LMB: Next layout, RMB: Menu")
            check_key(settings, "angle", 0.0)

            self.label.set_angle(settings["angle"])

            if settings["angle"] != 0.0:
                self.box.set_orientation(Gtk.Orientation.VERTICAL)

            update_image(self.image, "input-keyboard", self.settings["icon-size"], self.icons_path)

            self.set_property("name", settings["root-css-name"])
            if settings["css-name"]:
                self.label.set_property("name", settings["css-name"])
            else:
                self.label.set_property("name", "executor-label")

            if settings["tooltip-text"]:
                self.set_tooltip_text(settings["tooltip-text"])

            self.connect('button-press-event', self.on_button_press)
            self.connect('enter-notify-event', on_enter_notify_event)
            self.connect('leave-notify-event', on_leave_notify_event)

            self.build_box()
            self.refresh()
            self.show_all()

    def get_current_layout(self):
        if self.settings["device-name"] != "all":
            for k in self.keyboards:
                if k["name"] == self.settings["device-name"]:
                    return k["active_keymap"]
            return "unknown"
        else:
            for k in self.keyboards:
                if "keyboard" in k["name"]:
                    return k["active_keymap"]
            return self.keyboards[0]["layout"]

    def refresh(self):
        self.keyboards = list_keyboards()
        label = self.get_current_layout()
        if label:
            self.label.set_text(label)

    def build_box(self):
        if self.settings["icon-placement"] == "left":
            self.box.pack_start(self.image, False, False, 6)
        self.box.pack_start(self.label, False, False, 6)
        if self.settings["icon-placement"] != "left":
            self.box.pack_start(self.image, False, False, 6)

    def on_left_click(self):
        # apply to selected device, if any
        if self.settings["device-name"] != "all":
            hyprctl(f"switchxkblayout {self.settings['device-name']} next")
        # apply to all devices
        else:
            for name in self.keyboard_names:
                hyprctl(f"switchxkblayout {name} next")

        self.refresh()

    def on_right_click(self):
        menu = Gtk.Menu()
        for i in range(len(self.kb_layouts)):
            item = Gtk.MenuItem.new_with_label(self.kb_layouts[i])
            menu.append(item)
        menu.set_reserve_toggle_size(False)
        menu.show_all()
        menu.popup_at_widget(self.label, Gdk.Gravity.STATIC, Gdk.Gravity.STATIC, None)

    def on_button_press(self, widget, event):
        if event.button == 1:
            self.on_left_click()
        elif event.button == 3:
            self.on_right_click()
