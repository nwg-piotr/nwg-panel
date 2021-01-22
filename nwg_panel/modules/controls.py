#!/usr/bin/env python3

import threading

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, GtkLayerShell

from nwg_panel.tools import check_key, get_brightness, set_brightness, get_volume, set_volume, get_battery
from nwg_panel.common import icons_path


class Controls(Gtk.EventBox):
    def __init__(self, settings, position, alignment, width):
        self.settings = settings
        self.position = position
        self.alignment = alignment
        Gtk.EventBox.__init__(self)

        check_key(settings, "show-values", True)
        check_key(settings, "icon-size", 16)

        self.bri_icon_name = "wtf"
        self.bri_image = Gtk.Image.new_from_icon_name(self.bri_icon_name, Gtk.IconSize.MENU)
        self.bri_label = Gtk.Label("0%") if settings["show-values"] else None
        self.bri_slider = None
        self.icon_size = settings["icon-size"]

        self.vol_icon_name = "wtf"
        self.vol_image = Gtk.Image.new_from_icon_name(self.vol_icon_name, Gtk.IconSize.MENU)
        self.vol_label = Gtk.Label("0%") if settings["show-values"] else None

        self.bat_icon_name = "wtf"
        self.bat_image = Gtk.Image.new_from_icon_name(self.bat_icon_name, Gtk.IconSize.MENU)
        self.bat_label = Gtk.Label("0%") if settings["show-values"] else None

        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(self.box)

        check_key(settings, "interval", 1)
        check_key(settings, "icon-size", 16)
        check_key(settings, "css-name", "controls-label")
        check_key(settings, "components", ["brightness", "volume", "battery"])

        self.popup_window = PopupWindow(position, settings, width)

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
                    box.pack_start(self.bri_label, False, False, 0)

            if item == "volume":
                box.pack_start(self.vol_image, False, False, 4)
                if self.vol_label:
                    self.vol_label.set_property("name", self.settings["css-name"])
                    box.pack_start(self.vol_label, False, False, 0)

            if item == "battery":
                box.pack_start(self.bat_image, False, False, 4)
                if self.bat_label:
                    self.bat_label.set_property("name", self.settings["css-name"])
                    box.pack_start(self.bat_label, False, False, 0)

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
        icon_name = bri_icon_name(value)

        if icon_name != self.bri_icon_name:
            update_image(self.bri_image, icon_name, self.icon_size)
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
            update_image(self.bat_image, icon_name, self.icon_size)
            self.bat_icon_name = icon_name

        if self.bat_label:
            self.bat_label.set_text("{}%".format(value))
            
    def update_volume(self, value, switch):
        icon_name = vol_icon_name(value, switch)
            
        if icon_name != self.vol_icon_name:
            update_image(self.vol_image, icon_name, self.settings["icon-size"])
            self.vol_icon_name = icon_name

        if self.vol_label:
            self.vol_label.set_text("{}%".format(value))

    def on_button_press(self, w, event):
        if not self.popup_window.get_visible():
            self.popup_window.show_all()
        else:
            self.popup_window.hide()
        return False

    def on_enter_notify_event(self, widget, event):
        self.get_style_context().set_state(Gtk.StateFlags.SELECTED)
        return True

    def on_leave_notify_event(self, widget, event):
        self.get_style_context().set_state(Gtk.StateFlags.NORMAL)
        return True


class PopupWindow(Gtk.Window):
    def __init__(self, position, settings, width):
        Gtk.Window.__init__(self, type_hint=Gdk.WindowTypeHint.NORMAL)
        GtkLayerShell.init_for_window(self)
        check_key(settings, "css-name", "controls-window")
        self.set_property("name", settings["css-name"])
        self.icon_size = settings["icon-size"]

        self.connect("button-press-event", self.close_win)
        #self.connect("key-release-event", self.handle_keyboard)
        
        outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        h_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        outer_box.pack_start(h_box, True, True, 20)
        Gtk.Widget.set_size_request(h_box, width, 10)

        self.add(outer_box)
        v_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        h_box.pack_start(v_box, True, True, 30)

        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)

        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, 6)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, 6)
        # GtkLayerShell.set_keyboard_interactivity(self, True)

        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, 0)   # panel padding
        if settings["alignment"] == "left":
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        else:
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        if position == "bottom":
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
        else:
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)

        if "brightness" in settings["components"]:
            inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            v_box.pack_start(inner_box, False, False, 0)

            self.bri_icon_name = "wtf"
            self.bri_image = Gtk.Image.new_from_icon_name(self.bri_icon_name, Gtk.IconSize.MENU)

            icon_name = bri_icon_name(int(get_brightness()))
            if icon_name != self.bri_icon_name:
                update_image(self.bri_image, icon_name, self.icon_size)
                self.bri_icon_name = icon_name

            inner_box.pack_start(self.bri_image, False, False, 0)

            scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.HORIZONTAL, min=0, max=100, step=1)
            value = get_brightness()
            scale.set_value(value)
            scale.connect("value-changed", self.set_bri)

            inner_box.pack_start(scale, True, True, 5)
            
        if "volume" in settings["components"]:
            inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            v_box.pack_start(inner_box, False, False, 10)

            self.vol_icon_name = "wtf"
            self.vol_image = Gtk.Image.new_from_icon_name(self.vol_icon_name, Gtk.IconSize.MENU)

            vol, switch = get_volume()
            icon_name = vol_icon_name(vol, switch)

            if icon_name != self.vol_icon_name:
                update_image(self.vol_image, icon_name, self.icon_size)
                self.vol_icon_name = icon_name

            inner_box.pack_start(self.vol_image, False, False, 0)

            scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.HORIZONTAL, min=0, max=100, step=1)
            value, switch = get_volume()
            scale.set_value(value)
            scale.connect("value-changed", self.set_vol)

            inner_box.pack_start(scale, True, True, 5)

    def set_bri(self, slider):
        set_brightness(slider)
        icon_name = bri_icon_name(int(slider.get_value()))
        if icon_name != self.bri_icon_name:
            update_image(self.bri_image, icon_name, self.icon_size)
            self.bri_icon_name = icon_name

    def set_vol(self, slider):
        set_volume(slider)
        vol, switch = get_volume()
        icon_name = vol_icon_name(vol, switch)
        if icon_name != self.vol_icon_name:
            update_image(self.vol_image, icon_name, self.icon_size)
            self.vol_icon_name = icon_name
    
    def close_win(self, w, e):
        self.hide()
        
        return True
    
    def handle_keyboard(self, w, e):
        if e.type == Gdk.EventType.KEY_RELEASE and e.keyval == Gdk.KEY_Escape:
            self.close_win(w, e)
        return e


def bri_icon_name(value):
    icon_name = "display-brightness-low-symbolic"
    if value > 70:
        icon_name = "display-brightness-high-symbolic"
    elif value > 30:
        icon_name = "display-brightness-medium-symbolic"
    
    return icon_name


def vol_icon_name(value, switch):
    icon_name = "audio-volume-muted-symbolic"
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

    return icon_name


def update_image(image, icon_name, icon_size):
    if icons_path:
        path = "{}/{}.svg".format(icons_path, icon_name)
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                path, icon_size, icon_size)
            image.set_from_pixbuf(pixbuf)
        except Exception as e:
            print("update_image :: failed setting image from {}: {}".format(path, e))
    else:
        image.set_from_icon_name(icon_name, icon_size)
