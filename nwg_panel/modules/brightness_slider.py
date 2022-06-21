#!/usr/bin/env python3

import threading
import subprocess

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GLib, GtkLayerShell

from nwg_panel.tools import check_key, get_brightness, set_brightness, update_image, eprint
from nwg_panel.common import commands

class BrightnessSlider(Gtk.EventBox):
    def __init__(self, settings, icons_path=""):
        Gtk.EventBox.__init__(self)

        defaults = {
            "show-values": True,
            "icon-size": 16,
            "interval": 10,
            "hover-opens": False,
            "leave-closes": False,
            "root-css-name": "brightness-module",
            "css-name": "brightness-popup",
            "angle": 0.0,
            "popup-length": 256,
            "icon-placement": "start",
            "backlight-device": "",
            "slider-orientation": "vertical",
            "slider-inverted": True,
            "popup-icon-placement": "off",
            "popup-position": "off",
            "step-size": 2,
        }
        for key in defaults:
            check_key(settings, key, defaults[key])
        self.settings = settings

        self.set_property("name", self.settings["root-css-name"])

        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(self.box)

        self.icons_path = icons_path
        self.icon_size = settings["icon-size"]
        self.bri_icon_name = "view-refresh-symbolic"
        self.bri_image = Gtk.Image.new_from_icon_name(self.bri_icon_name, Gtk.IconSize.MENU)

        self.bri_label = Gtk.Label() if settings["show-values"] else None
        self.bri_value = 0

        self.popup_window = PopupWindow(self, settings, icons_path=self.icons_path)

        if settings["angle"] != 0.0:
            self.box.set_orientation(Gtk.Orientation.VERTICAL)
            self.bri_label.set_angle(settings["angle"])

        # events
        self.connect('button-press-event', self.on_button_press)
        self.connect('enter-notify-event', self.on_enter_notify_event)
        self.connect('leave-notify-event', self.on_leave_notify_event)
        if self.settings["step-size"] > 0:
            self.add_events(Gdk.EventMask.SCROLL_MASK) 
            self.connect('scroll-event', self.on_scroll)

        self.build_box()

        self.refresh()
        Gdk.threads_add_timeout_seconds(GLib.PRIORITY_LOW, 5, self.refresh)

    def build_box(self):
        if self.settings["icon-placement"] == "start":
            self.box.pack_start(self.bri_image, False, False, 2)
            
        if self.bri_label:
            self.box.pack_start(self.bri_label, False, False, 2)

        if self.settings["icon-placement"] == "end":
            self.box.pack_start(self.bri_image, False, False, 2)

    def refresh(self):
        thread = threading.Thread(target=self.refresh_output)
        thread.daemon = True
        thread.start()

        return True

    def refresh_output(self):
        try:
            GLib.idle_add(self.update_brightness)
        except Exception as e:
            print(e)

        return False

    def update_brightness(self):
        self.bri_value = get_brightness(device=self.settings["backlight-device"])
        
        icon_name = bri_icon_name(self.bri_value)

        if icon_name != self.bri_icon_name:
            update_image(self.bri_image, icon_name, self.icon_size, self.icons_path)
            self.bri_icon_name = icon_name

        if self.bri_label:
            self.bri_label.set_text("{}%".format(self.bri_value))
    
    def on_button_press(self, w, event):
        if not self.popup_window.get_visible():
            self.popup_window.update_position()
            self.popup_window.show_all()
        else:
            self.popup_window.hide()
        
        return False
    
    def on_scroll(self, w, event):
        if event.direction == Gdk.ScrollDirection.UP:
            self.bri_value += self.settings["step-size"]
            self.popup_window.bri_scale.set_value(self.bri_value)
            self.update_brightness()
        elif event.direction == Gdk.ScrollDirection.DOWN:
            self.bri_value -= self.settings["step-size"]
            self.popup_window.bri_scale.set_value(self.bri_value)
            self.update_brightness()
    
        return False

    def on_enter_notify_event(self, widget, event):
        if self.settings["hover-opens"]:
            if not self.popup_window.get_visible():
                self.popup_window.update_position()
                self.popup_window.show_all()
        else:
            widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
            widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)

        # cancel popup window close, as it's probably unwanted ATM
        self.popup_window.on_window_enter()

        return True

    def on_leave_notify_event(self, widget, event):
        widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
        widget.unset_state_flags(Gtk.StateFlags.SELECTED)
        return True
        
    def get_panel_window(self):
        parent = self
        while True:
            parent = parent.get_parent()
            if type(parent) == Gtk.Window:
                return parent
            elif parent == None:
                return None

class PopupWindow(Gtk.Window):
    def __init__(self, parent, settings, icons_path=""):
        Gtk.Window.__init__(self, type_hint=Gdk.WindowTypeHint.DOCK, type=Gtk.WindowType.POPUP)

        self.parent = parent
        self.settings = settings
        self.icon_size = settings["icon-size"]
        self.icons_path = icons_path
        self.src_tag = 0

        self.set_property("name", self.settings["css-name"])
        
        self.connect("show", self.on_window_show)
        if settings["leave-closes"]:
            self.connect("leave_notify_event", self.on_window_exit)
            self.connect("enter_notify_event", self.on_window_enter)

        eb = Gtk.EventBox()
        eb.set_above_child(False)

        self.box = Gtk.Box(spacing=0)
        if self.settings["slider-orientation"] == "vertical":
            self.box.set_orientation(Gtk.Orientation.VERTICAL)
        elif self.settings["slider-orientation"] == "horizontal":
            self.box.set_orientation(Gtk.Orientation.HORIZONTAL)
            
        eb.add(self.box)
        self.add(eb)

        self.bri_icon_name = "view-refresh-symbolic"
        self.bri_image = Gtk.Image.new_from_icon_name(self.bri_icon_name, Gtk.IconSize.MENU)

        if self.settings["slider-orientation"] == "vertical":
            self.bri_scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.VERTICAL, min=0, max=100, step=1)
        elif self.settings["slider-orientation"] == "horizontal":
            self.bri_scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.HORIZONTAL, min=0, max=100, step=1)
        self.bri_scale.set_inverted(self.settings["slider-inverted"])
        self.bri_scale_handler = self.bri_scale.connect("value-changed", self.set_bri)

        self.build_box()

        Gdk.threads_add_timeout(GLib.PRIORITY_LOW, 500, self.refresh)
    
    def build_box(self):
        if self.settings["popup-icon-placement"] == "start":
            self.box.pack_start(self.bri_image, False, False, 6)
        
        self.box.pack_start(self.bri_scale, True, True, 5)
        
        if self.settings["popup-icon-placement"] == "end":
            self.box.pack_start(self.bri_image, False, False, 6)

    def refresh(self, *args):
        if self.get_visible():
            if self.parent.bri_icon_name != self.bri_icon_name:
                update_image(self.bri_image, self.parent.bri_icon_name, self.icon_size, self.icons_path)
                self.bri_icon_name = self.parent.bri_icon_name

            with self.bri_scale.handler_block(self.bri_scale_handler):
                self.bri_scale.set_value(self.parent.bri_value)

        return True

    def on_window_exit(self, w, e):
        if self.get_visible():
            self.src_tag = GLib.timeout_add_seconds(1, self.hide_and_clear_tag)
        return True

    def hide_and_clear_tag(self):
        self.hide()
        self.src_tag = 0

    def on_window_enter(self, *args):
        if self.src_tag > 0:
            GLib.Source.remove(self.src_tag)
            self.src_tag = 0
        return True

    def on_window_show(self, *args):
        self.src_tag = 0
        self.refresh()

    def set_bri(self, slider):
        self.parent.bri_value = int(slider.get_value())
        set_brightness(self.parent.bri_value, device=self.settings["backlight-device"])
    
    def update_position(self):
        panel = self.get_transient_for()
        if panel == None:
            panel = self.parent.get_panel_window()
            if panel:
                self.set_transient_for(panel)
        
        if panel:
            panel_width, panel_height = panel.get_size()
            if self.settings["popup-position"] == "top":
                button_start = self.parent.get_window().get_position().x
                button_length = self.parent.get_allocated_width()
                button_midpoint = button_start + (button_length / 2)

                if self.settings["slider-orientation"] == "horizontal":
                    popup_width = self.settings["popup-length"]
                    popup_height = max(50, button_length)
                elif self.settings["slider-orientation"] == "vertical":
                    popup_width = max(50, button_length)
                    popup_height = self.settings["popup-length"]
                
                x = button_midpoint - (popup_width / 2)
                y = -popup_height

                if x + popup_width > panel_width:
                    x = panel_width - popup_width
                
                if x < 0:
                    x = 0
            elif self.settings["popup-position"] == "bottom":
                button_start = self.parent.get_window().get_position().x
                button_length = self.parent.get_allocated_width()
                button_midpoint = button_start + (button_length / 2)

                if self.settings["slider-orientation"] == "horizontal":
                    popup_width = self.settings["popup-length"]
                    popup_height = max(50, button_length)
                elif self.settings["slider-orientation"] == "vertical":
                    popup_width = max(50, button_length)
                    popup_height = self.settings["popup-length"]
                
                x = button_midpoint - (popup_width / 2)
                y = panel_height

                if x + popup_width > panel_width:
                    x = panel_width - popup_width
                
                if x < 0:
                    x = 0
            elif self.settings["popup-position"] == "left":
                button_start = self.parent.get_window().get_position().y
                button_length = self.parent.get_allocated_height()
                button_midpoint = button_start + (button_length / 2)

                if self.settings["slider-orientation"] == "horizontal":
                    popup_width = self.settings["popup-length"]
                    popup_height = max(50, button_length)
                elif self.settings["slider-orientation"] == "vertical":
                    popup_width = max(50, button_length)
                    popup_height = self.settings["popup-length"]
                
                x = -popup_width
                y = button_midpoint - (popup_height / 2)

                if y + popup_height > panel_height:
                    y = panel_height - popup_height
                
                if y < 0:
                    y = 0
            elif self.settings["popup-position"] == "right":
                button_start = self.parent.get_window().get_position().y
                button_length = self.parent.get_allocated_height()
                button_midpoint = button_start + (button_length / 2)

                if self.settings["slider-orientation"] == "horizontal":
                    popup_width = self.settings["popup-length"]
                    popup_height = max(50, button_length)
                elif self.settings["slider-orientation"] == "vertical":
                    popup_width = max(50, button_length)
                    popup_height = self.settings["popup-length"]
                
                x = panel_width
                y = button_midpoint - (popup_height / 2)

                if y + popup_height > panel_height:
                    y = panel_height - popup_height
                
                if y < 0:
                    y = 0
                
            Gtk.Widget.set_size_request(self.box, popup_width, popup_height)
            self.move(x, y)

def bri_icon_name(value):
    icon_name = "display-brightness-low-symbolic"
    if value > 70:
        icon_name = "display-brightness-high-symbolic"
    elif value > 30:
        icon_name = "display-brightness-medium-symbolic"

    return icon_name
