#!/usr/bin/env python3
import json
import os

import gi

from nwg_panel.tools import check_key, update_image, eprint, hyprctl

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk


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

        if os.getenv("SWAYSOCK"):
            from i3ipc import Connection
            self.i3 = Connection()
            self.compositor = "sway"
        elif os.getenv("HYPRLAND_INSTANCE_SIGNATURE"):
            self.compositor = "Hyprland"
        else:
            self.compositor = ""
            eprint("Neither sway nor Hyprland detected, this won't work")

        if self.compositor:
            self.keyboards = self.list_keyboards()
            if self.keyboards:
                self.keyboard_names = []
                for k in self.keyboards:
                    if self.compositor == "Hyprland":
                        self.keyboard_names.append(k["name"])
                    # On sway some devices may be listed twice, let's add them just once
                    elif k.identifier not in self.keyboard_names:
                        self.keyboard_names.append(k.identifier)

                self.kb_layouts = self.get_kb_layouts()

                check_key(settings, "keyboard-device-sway", "")
                check_key(settings, "keyboard-device-hyprland", "")
                self.device_name = settings["keyboard-device-sway"] if self.compositor == "sway" else settings[
                    "keyboard-device-hyprland"]

                check_key(settings, "root-css-name", "root-executor")
                check_key(settings, "css-name", "")
                check_key(settings, "icon-placement", "left")
                check_key(settings, "icon-size", 16)
                check_key(settings, "show-icon", True)
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

                self.connect('button-release-event', self.on_button_release)
                self.connect('enter-notify-event', on_enter_notify_event)
                self.connect('leave-notify-event', on_leave_notify_event)

                self.build_box()
                label = self.get_current_layout()
                if label:
                    self.label.set_text(label)
                self.show_all()
            else:
                print("KeyboardLayout module: failed listing devices, won't create UI, sorry.")

    def list_keyboards(self):
        if self.compositor == "Hyprland":
            o = hyprctl("j/devices")
            devices = json.loads(o)
            keyboards = devices["keyboards"] if "keyboards" in devices else []
        else:
            inputs = self.i3.get_inputs()
            keyboards = []
            for i in inputs:
                if i.type == "keyboard":
                    keyboards.append(i)

        return keyboards

    def get_kb_layouts(self):
        if self.compositor == "Hyprland":
            o = hyprctl("j/getoption input:kb_layout")
            option = json.loads(o)
            if option and "str" in option:
                return option["str"].split(",")
            return []
        elif self.compositor == "sway":
            layout_names = []
            if self.keyboards:
                for k in self.keyboards:
                    for name in k.xkb_layout_names:
                        if name not in layout_names:
                            layout_names.append(name)
            return layout_names

    def get_current_layout(self):
        if self.compositor == "Hyprland":
            if self.device_name:
                for k in self.keyboards:
                    if k["name"] == self.device_name:
                        return k["active_keymap"]
                return "unknown"
            else:
                for k in self.keyboards:
                    if "keyboard" in k["name"]:
                        return k["active_keymap"]
                return self.keyboards[0]["layout"]
        elif self.compositor == "sway":
            for k in self.keyboards:
                if "keyboard" in k.identifier:
                    return k.xkb_active_layout_name
                return self.keyboards[0].xkb_active_layout_name
            return "unknown"

    def refresh(self):
        self.keyboards = self.list_keyboards()
        label = self.get_current_layout()
        if label:
            self.label.set_text(label)

    def build_box(self):
        if self.settings["show-icon"] and self.settings["icon-placement"] == "left":
            self.box.pack_start(self.image, False, False, 3)
        self.box.pack_start(self.label, False, False, 3)
        if self.settings["show-icon"] and self.settings["icon-placement"] != "left":
            self.box.pack_start(self.image, False, False, 3)

    def on_left_click(self):
        if self.compositor == "Hyprland":
            if self.device_name:
                # apply to selected device
                hyprctl(f"switchxkblayout {self.device_name} next")
            else:
                # apply to all devices
                for name in self.keyboard_names:
                    hyprctl(f"switchxkblayout {name} next")
        elif self.compositor == "sway":
            # apply to all devices of type:keyboard
            self.i3.command(f'input type:keyboard xkb_switch_layout next')

        self.refresh()

    def on_menu_item(self, item, idx):
        if self.compositor == "Hyprland":
            if self.device_name:
                # apply to selected device
                hyprctl(f'switchxkblayout {self.device_name} {idx}')
            else:
                # apply to all devices
                for name in self.keyboard_names:
                    hyprctl(f'switchxkblayout {name} {idx}')
        elif self.compositor == "sway":
            # apply to all devices of type:keyboard
            self.i3.command(f'input type:keyboard xkb_switch_layout {idx}')

        self.refresh()

    def on_right_click(self):
        menu = Gtk.Menu()
        for i in range(len(self.kb_layouts)):
            item = Gtk.MenuItem.new_with_label(self.kb_layouts[i])
            item.connect("activate", self.on_menu_item, i)
            menu.append(item)
        menu.set_reserve_toggle_size(False)
        menu.show_all()
        menu.popup_at_widget(self.label, Gdk.Gravity.STATIC, Gdk.Gravity.STATIC, None)

    def on_button_release(self, widget, event):
        if event.button == 1:
            self.on_left_click()
        elif event.button == 3:
            self.on_right_click()
