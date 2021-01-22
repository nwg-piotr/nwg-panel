#!/usr/bin/env python3

import threading

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf

from nwg_panel.tools import check_key, get_brightness, get_volume, get_battery
from nwg_panel.common import icons_path


class Controls(Gtk.EventBox):
    def __init__(self, settings):
        self.settings = settings
        Gtk.EventBox.__init__(self)

        self.bri_icon_name = "wtf"
        self.bri_image = Gtk.Image.new_from_icon_name(self.bri_icon_name, Gtk.IconSize.MENU)
        self.bri_label = Gtk.Label("0%") if settings["show-values"] else None

        self.vol_icon_name = "wtf"
        self.vol_image = Gtk.Image.new_from_icon_name(self.vol_icon_name, Gtk.IconSize.MENU)
        self.vol_label = Gtk.Label("0%") if settings["show-values"] else None

        self.bat_icon_name = "wtf"
        self.bat_image = Gtk.Image.new_from_icon_name(self.bat_icon_name, Gtk.IconSize.MENU)
        self.bat_label = Gtk.Label("0%") if settings["show-values"] else None

        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(self.box)

        check_key(settings, "show-values", True)
        check_key(settings, "interval", 1)
        check_key(settings, "icon-size", 16)
        check_key(settings, "css-name", "controls-label")
        check_key(settings, "components", ["brightness", "volume", "battery"])

        self.connect('button-press-event', self.on_button_press)
        self.connect('enter-notify-event', self.on_enter_notify_event)
        self.connect('leave-notify-event', self.on_leave_notify_event)

        self.build_box()
        self.refresh()
        self.refresh_bat()

        if settings["interval"] > 0:
            Gdk.threads_add_timeout_seconds(GLib.PRIORITY_LOW, settings["interval"], self.refresh)

        if "battery" in settings["components"]:
            Gdk.threads_add_timeout_seconds(GLib.PRIORITY_LOW, 5, self.refresh_bat)

    def build_box(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.box.pack_start(box, False, False, 6)
        for item in self.settings["components"]:
            if item == "brightness":
                box.pack_start(self.bri_image, False, False, 4)
                if self.bri_label:
                    self.bri_label.set_property("name", self.settings["css-name"])
                    box.pack_start(self.bri_label, False, False, 2)

            if item == "volume":
                box.pack_start(self.vol_image, False, False, 4)
                if self.vol_label:
                    self.vol_label.set_property("name", self.settings["css-name"])
                    box.pack_start(self.vol_label, False, False, 2)

            if item == "battery":
                box.pack_start(self.bat_image, False, False, 4)
                if self.bat_label:
                    self.bat_label.set_property("name", self.settings["css-name"])
                    box.pack_start(self.bat_label, False, False, 2)

    def get_output(self):
        if "brightness" in self.settings["components"]:
            try:
                value = get_brightness()
                GLib.idle_add(self.update_brightness, value)
            except Exception as e:
                print(e)
                
        if "volume" in self.settings["components"]:
            try:
                value, switch = get_volume()
                GLib.idle_add(self.update_volume, value, switch)
            except Exception as e:
                print(e)

        return False

    def get_bat_output(self):
        if "battery" in self.settings["components"]:
            try:
                msg, value = get_battery()
                GLib.idle_add(self.update_battery, value)
            except Exception as e:
                print(e)

    def refresh(self):
        thread = threading.Thread(target=self.get_output)
        thread.daemon = True
        thread.start()
        return True

    # No point in checking battery data more often that every 5 seconds:
    # `upower` / `acpi` response does not change that quickly.
    def refresh_bat(self):
        thread = threading.Thread(target=self.get_bat_output)
        thread.daemon = True
        thread.start()
        return True

    def update_brightness(self, value):
        if value > 70:
            icon_name = "display-brightness-high-symbolic"
        elif value > 30:
            icon_name = "display-brightness-medium-symbolic"
        else:
            icon_name = "display-brightness-low-symbolic"

        if icon_name != self.bri_icon_name:
            self.update_image(self.bri_image, icon_name)
            self.bri_icon_name = icon_name

        if self.bri_label:
            self.bri_label.set_text("{}%".format(value))
            
    def update_battery(self, value):
        if value > 95:
            icon_name = "battery-full-symbolic"
        elif value > 50:
            icon_name = "battery-good-symbolic"
        elif value > 20:
            icon_name = "battery-low-symbolic"
        else:
            icon_name = "battery-empty-symbolic"
            
        if icon_name != self.bat_icon_name:
            self.update_image(self.bat_image, icon_name)
            self.bat_icon_name = icon_name

        if self.bat_label:
            self.bat_label.set_text("{}%".format(value))
            
    def update_volume(self, value, switch):
        if switch:
            if value is not None:
                if value > 70:
                    icon_name = "audio-volume-high-symbolic"
                elif value > 30:
                    icon_name = "audio-volume-medium-symbolic"
                else:
                    icon_name = "audio-volume-low-symbolic"
            else:
                icon_name = "audio-volume-muted-symbolic"
        else:
            icon_name = "audio-volume-muted-symbolic"
            
        if icon_name != self.vol_icon_name:
            self.update_image(self.vol_image, icon_name)
            self.vol_icon_name = icon_name

        if self.vol_label:
            self.vol_label.set_text("{}%".format(value))

    def update_image(self, image, icon_name):
        if icons_path:
            path = "{}/{}.svg".format(icons_path, icon_name)
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    path, self.settings["icon-size"], self.settings["icon-size"])
                image.set_from_pixbuf(pixbuf)
            except Exception as e:
                print("update_image :: failed setting image from {}: {}".format(path, e))
        else:
            image.set_from_icon_name(icon_name, self.settings["icon-size"])

    def on_button_press(self, w, event):
        print("CC clicked")
        menu = Gtk.Menu()
        item = Gtk.MenuItem.new_with_label("gtk-layer-shell")
        menu.append(item)
        item = Gtk.MenuItem.new_with_label("is a very fucking awesome")
        menu.append(item)
        item = Gtk.MenuItem.new_with_label("thing!")
        menu.append(item)
        menu.show_all()
        menu.popup_at_widget(self, Gdk.Gravity.SOUTH, Gdk.Gravity.NORTH, None)

    def on_enter_notify_event(self, widget, event):
        self.get_style_context().set_state(Gtk.StateFlags.SELECTED)

    def on_leave_notify_event(self, widget, event):
        self.get_style_context().set_state(Gtk.StateFlags.NORMAL)