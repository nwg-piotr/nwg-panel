#!/usr/bin/env python3
import os.path

from gi.repository import GLib

import subprocess
import threading
from datetime import datetime

from nwg_panel.tools import check_key, get_config_dir, load_json, save_json

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk, GtkLayerShell


class Clock(Gtk.EventBox):
    def __init__(self, settings):
        self.settings = settings
        Gtk.EventBox.__init__(self)
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(self.box)
        self.label = Gtk.Label.new("")

        check_key(settings, "root-css-name", "root-clock")
        check_key(settings, "css-name", "clock")
        check_key(settings, "tooltip-text", "")
        check_key(settings, "tooltip-date-format", False)
        check_key(settings, "on-left-click", "")
        check_key(settings, "on-right-click", "")
        check_key(settings, "on-middle-click", "")
        check_key(settings, "on-scroll-up", "")
        check_key(settings, "on-scroll-down", "")

        check_key(settings, "interval", 1)
        check_key(settings, "angle", 0.0)

        defaults = {"root-css-name": "root-clock",
                    "css-name": "clock",
                    "popup-css-name": "calendar",
                    "tooltip-text": "",
                    "tooltip-date-format": False,
                    "on-right-click": "",
                    "on-middle-click": "",
                    "on-scroll-up": "",
                    "on-scroll-down": "",
                    "interval": 1,
                    "angle": 0.0,
                    "calendar-path": ""}

        for key in defaults:
            check_key(settings, key, defaults[key])

        self.calendar = {}
        if settings["calendar-path"]:
            c = load_json(os.path.join(settings["calendar-path"], "calendar.json"))
            if c is not None:
                self.calendar = c
            else:
                save_json(self.calendar, os.path.join(settings["calendar-path"], "calendar.json"))
        else:
            config_dir = get_config_dir()
            c = load_json(os.path.join(config_dir, "calendar.json"))
            if c is not None:
                self.calendar = c
            else:
                save_json(self.calendar, os.path.join(config_dir, "calendar.json"))

        print("self.calendar = ", self.calendar)
        self.popup = Gtk.Window()

        self.set_property("name", settings["root-css-name"])
        self.label.set_property("name", settings["css-name"])

        self.label.set_angle(settings["angle"])

        if settings["tooltip-text"]:
            self.set_tooltip_text(settings["tooltip-text"])

        if "format" not in settings:
            self.settings["format"] = "%a, %d. %b  %H:%M:%S"

        self.connect('button-press-event', self.on_button_press)
        self.connect('enter-notify-event', self.on_enter_notify_event)
        self.connect('leave-notify-event', self.on_leave_notify_event)
        if settings["on-scroll-up"] or settings["on-scroll-down"]:
            self.add_events(Gdk.EventMask.SCROLL_MASK)
            self.connect('scroll-event', self.on_scroll)

        self.build_box()
        self.refresh()

        if settings["interval"] > 0:
            Gdk.threads_add_timeout_seconds(GLib.PRIORITY_LOW, settings["interval"], self.refresh)

    def update_widget(self, output, tooltip=""):
        self.label.set_text(output)
        if self.settings["tooltip-date-format"] and tooltip:
            self.set_tooltip_text(tooltip)

        return False

    def get_output(self):
        now = datetime.now()
        try:
            time = now.strftime(self.settings["format"])
            tooltip = now.strftime(self.settings["tooltip-text"]) if self.settings["tooltip-date-format"] else ""
            GLib.idle_add(self.update_widget, time, tooltip)
        except Exception as e:
            print(e)

    def refresh(self):
        thread = threading.Thread(target=self.get_output)
        thread.daemon = True
        thread.start()
        return True

    def build_box(self):
        self.box.pack_start(self.label, False, False, 4)
        self.label.show()

    def on_enter_notify_event(self, widget, event):
        widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
        widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)

    def on_leave_notify_event(self, widget, event):
        widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
        widget.unset_state_flags(Gtk.StateFlags.SELECTED)

    def on_button_press(self, widget, event):
        if event.button == 1:
            # self.launch(self.settings["on-left-click"])
            self.display_calendar_window()
        elif event.button == 2 and self.settings["on-middle-click"]:
            self.launch(self.settings["on-middle-click"])
        elif event.button == 3 and self.settings["on-right-click"]:
            self.launch(self.settings["on-right-click"])

    def on_scroll(self, widget, event):
        if event.direction == Gdk.ScrollDirection.UP and self.settings["on-scroll-up"]:
            self.launch(self.settings["on-scroll-up"])
        elif event.direction == Gdk.ScrollDirection.DOWN and self.settings["on-scroll-up"]:
            self.launch(self.settings["on-scroll-down"])
        else:
            print("No command assigned")

    def launch(self, cmd):
        print("Executing '{}'".format(cmd))
        subprocess.Popen('exec {}'.format(cmd), shell=True)

    def display_calendar_window(self):
        if self.popup.is_visible():
            self.popup.close()
            self.popup.destroy()
            return

        self.popup.destroy()

        self.popup = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
        GtkLayerShell.init_for_window(self.popup)
        GtkLayerShell.set_layer(self.popup, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(self.popup, GtkLayerShell.Edge.TOP, 1)

        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        vbox.set_property("margin", 6)
        self.popup.add(vbox)
        cal = Gtk.Calendar.new()
        cal.set_detail_width_chars(10)
        vbox.pack_start(cal, False, False, 0)

        self.popup.show_all()

        self.popup.set_size_request(self.popup.get_allocated_width() * 1.5, 0)