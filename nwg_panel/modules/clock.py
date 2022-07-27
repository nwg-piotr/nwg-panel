#!/usr/bin/env python3
import os.path

from gi.repository import GLib

import subprocess
import threading
from datetime import datetime

from nwg_panel.tools import check_key, get_config_dir, load_json, save_json, update_image

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk, GtkLayerShell


class Clock(Gtk.EventBox):
    def __init__(self, settings, icons_path=""):
        self.path = ""
        self.cal = None
        self.note_box = None
        self.popup = None
        self.note_entry = None
        self.icons_path = icons_path

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
            self.path = os.path.join(settings["calendar-path"], "calendar.json")
            c = load_json(self.path)
            if c is not None:
                self.calendar = c
            else:
                save_json(self.calendar, self.path)
        else:
            config_dir = get_config_dir()
            self.path = os.path.join(config_dir, "calendar.json")
            c = load_json(self.path)
            if c is not None:
                self.calendar = c
            else:
                save_json(self.calendar, self.path)

        print("self.calendar = ", self.calendar)
        print("self.path = ", self.path)

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
        if self.popup:
            if self.popup.is_visible():
                self.popup.destroy()
                return

            self.popup.destroy()

        self.popup = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
        self.popup.connect("key-release-event", self.handle_keyboard)
        GtkLayerShell.init_for_window(self.popup)
        GtkLayerShell.set_layer(self.popup, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(self.popup, GtkLayerShell.Edge.TOP, 1)
        GtkLayerShell.set_keyboard_interactivity(self.popup, True)

        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        vbox.set_property("margin", 6)
        self.popup.add(vbox)
        self.cal = Gtk.Calendar.new()
        self.cal.connect("day-selected", self.on_day_selected)
        vbox.pack_start(self.cal, False, False, 0)

        self.popup.show_all()

        self.note_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        self.note_entry = Gtk.Entry()
        self.note_entry.set_property("margin-top", 6)
        self.note_entry.connect("changed", self.on_note_changed)
        vbox.pack_start(self.note_box, False, False, 0)
        self.note_box.pack_start(self.note_entry, True, True, 0)
        btn = Gtk.Button()
        img = Gtk.Image()
        btn.set_image(img)
        update_image(img, "gtk-close", 32, self.icons_path)
        btn.set_tooltip_text("Cancel & close")
        btn.connect("clicked", self.cancel_close_popup)
        btn.set_always_show_image(True)
        self.note_box.pack_start(btn, False, False, 0)

        btn = Gtk.Button()
        img = Gtk.Image()
        btn.set_image(img)
        update_image(img, "gtk-apply", 24, self.icons_path)
        btn.set_tooltip_text("Apply & close")
        btn.connect("clicked", self.apply_close_popup)
        btn.set_always_show_image(True)
        self.note_box.pack_start(btn, False, False, 0)

        self.popup.set_size_request(self.popup.get_allocated_width() * 2, 0)

    def cancel_close_popup(self, *args):
        self.popup.destroy()

    def apply_close_popup(self, *args):
        c = {}
        if len(self.calendar) > 0:
            for key_year in self.calendar:
                if len(self.calendar[key_year]) > 0:
                    for key_month in self.calendar[key_year]:
                        if len(self.calendar[key_year][key_month]) > 0:
                            for key_day in self.calendar[key_year][key_month]:
                                if self.calendar[key_year][key_month][key_day]:
                                    if key_year not in c:
                                        c[key_year] = {}
                                    if key_month not in c[key_year]:
                                        c[key_year][key_month] = {}
                                    note = self.calendar[key_year][key_month][key_day]
                                    if note:
                                        c[key_year][key_month][key_day] = note
        print("c = ", c)
        save_json(c, self.path)
        self.popup.destroy()

    def handle_keyboard(self, win, event):
        if event.type == Gdk.EventType.KEY_RELEASE and event.keyval == Gdk.KEY_Escape:
            self.popup.destroy()

    def on_day_selected(self, cal):
        y, m, d = cal.get_date()
        try:
            self.note_entry.set_text(self.calendar[y][m][d])
        except KeyError:
            self.note_entry.set_text("")
        self.note_box.show_all()

    def on_note_changed(self, eb):
        y, m, d = self.cal.get_date()
        if y not in self.calendar:
            self.calendar[y] = {}
        if m not in self.calendar[y]:
            self.calendar[y][m] = {}
        note = eb.get_text()
        if note:
            self.calendar[y][m][d] = eb.get_text()
        elif d in self.calendar[y][m]:
            self.calendar[y][m].pop(d, None)
        print(self.calendar)
