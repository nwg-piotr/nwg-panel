#!/usr/bin/env python3
import os.path

from gi.repository import GLib

import subprocess
from datetime import datetime

from nwg_panel.tools import (check_key, eprint, local_dir, load_json, save_json, update_image, update_gtk_entry,
                             create_background_task, cmd_through_compositor)

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk, GtkLayerShell


class Clock(Gtk.EventBox):
    def __init__(self, settings, icons_path=""):
        self.reminder_img_updated = False
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

        defaults = {"root-css-name": "root-clock",
                    "css-name": "clock",
                    "tooltip-text": "",
                    "tooltip-date-format": False,
                    "on-right-click": "",
                    "on-middle-click": "",
                    "on-scroll-up": "",
                    "on-scroll-down": "",
                    "interval": 1,
                    "angle": 0.0,
                    "calendar-path": "",
                    "calendar-css-name": "calendar-window",
                    "calendar-placement": "top",
                    "calendar-margin-horizontal": 0,
                    "calendar-margin-vertical": 0,
                    "calendar-icon-size": 24,
                    "calendar-interval": 60,
                    "calendar-on": True}

        for key in defaults:
            check_key(settings, key, defaults[key])

        self.reminder_img = Gtk.Image()

        self.calendar = {}

        self.set_property("name", settings["root-css-name"])
        self.label.set_property("name", settings["css-name"])

        self.label.set_angle(settings["angle"])

        if settings["tooltip-text"]:
            self.set_tooltip_text(settings["tooltip-text"])

        if "format" not in settings:
            self.settings["format"] = "%a, %d. %b  %H:%M:%S"

        self.connect('button-release-event', self.on_button_release)
        if self.settings["calendar-on"] or self.settings["on-middle-click"] or self.settings["on-right-click"] or \
                self.settings["on-scroll-up"] or self.settings["on-scroll-down"]:
            self.connect('enter-notify-event', self.on_enter_notify_event)
        self.connect('leave-notify-event', self.on_leave_notify_event)
        if settings["on-scroll-up"] or settings["on-scroll-down"]:
            self.add_events(Gdk.EventMask.SCROLL_MASK)
            self.connect('scroll-event', self.on_scroll)

        self.load_calendar()
        self.build_box()
        self.refresh()

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

        ymd = now.strftime("%Y#%m#%d").split("#")
        y = ymd[0]
        try:
            month = int(ymd[1]) - 1
            m = str(month)
        except:
            m = None
        d = ymd[2]
        if self.has_note(y, m, d):
            if not self.reminder_img_updated:
                update_image(self.reminder_img, "gtk-apply", self.settings["calendar-icon-size"], self.icons_path)
                self.reminder_img_updated = True
            self.reminder_img.set_visible(True)
        else:
            self.reminder_img.set_visible(False)

    def refresh(self):
        thread = create_background_task(self.get_output, self.settings["interval"])
        thread.start()

        thread = create_background_task(self.reload_calendar, self.settings["calendar-interval"])
        thread.start()

    def build_box(self):
        if self.settings["calendar-on"]:
            self.box.pack_start(self.reminder_img, False, False, 0)
        self.box.pack_start(self.label, False, False, 6)

    def on_enter_notify_event(self, widget, event):
        widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
        widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)

    def on_leave_notify_event(self, widget, event):
        widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
        widget.unset_state_flags(Gtk.StateFlags.SELECTED)

    def on_button_release(self, widget, event):
        if event.button == 1:
            if self.settings["calendar-on"]:
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
        cmd = cmd_through_compositor(cmd)

        print(f"Executing: {cmd}")
        subprocess.Popen('{}'.format(cmd), shell=True)

    def display_calendar_window(self):
        if self.popup:
            if self.popup.is_visible():
                self.popup.destroy()
                return

            self.popup.destroy()

        self.load_calendar()

        self.popup = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
        self.popup.set_property("name", self.settings["calendar-css-name"])
        self.popup.connect("key-release-event", self.handle_keyboard)
        GtkLayerShell.init_for_window(self.popup)
        GtkLayerShell.set_layer(self.popup, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_keyboard_mode(self.popup, GtkLayerShell.KeyboardMode.ON_DEMAND)

        if self.settings["calendar-placement"] in ["top-left", "top", "top-right"]:
            GtkLayerShell.set_anchor(self.popup, GtkLayerShell.Edge.TOP, 1)
        elif self.settings["calendar-placement"] in ["bottom-left", "bottom", "bottom-right"]:
            GtkLayerShell.set_anchor(self.popup, GtkLayerShell.Edge.BOTTOM, 1)

        if self.settings["calendar-placement"] in ["top-left", "bottom-left"]:
            GtkLayerShell.set_anchor(self.popup, GtkLayerShell.Edge.LEFT, 1)
        elif self.settings["calendar-placement"] in ["top-right", "bottom-right"]:
            GtkLayerShell.set_anchor(self.popup, GtkLayerShell.Edge.RIGHT, 1)

        GtkLayerShell.set_margin(self.popup, GtkLayerShell.Edge.TOP, self.settings["calendar-margin-vertical"])
        GtkLayerShell.set_margin(self.popup, GtkLayerShell.Edge.BOTTOM, self.settings["calendar-margin-vertical"])
        GtkLayerShell.set_margin(self.popup, GtkLayerShell.Edge.RIGHT, self.settings["calendar-margin-horizontal"])
        GtkLayerShell.set_margin(self.popup, GtkLayerShell.Edge.LEFT, self.settings["calendar-margin-horizontal"])

        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        vbox.set_property("margin", 6)
        self.popup.add(vbox)
        self.cal = Gtk.Calendar.new()
        self.cal.connect("day-selected", self.on_day_selected)
        self.cal.connect("next-month", self.mark_days)
        self.cal.connect("prev-month", self.mark_days)
        self.cal.connect("next-year", self.mark_days)
        self.cal.connect("prev-year", self.mark_days)
        vbox.pack_start(self.cal, False, False, 0)

        self.popup.show_all()
        self.mark_days()

        self.note_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        self.note_entry = Gtk.Entry()
        self.note_entry.set_property("margin-top", 6)
        self.note_entry.connect("changed", self.on_note_changed)
        self.note_entry.connect("icon-release", self.on_note_icon_click)
        update_gtk_entry(self.note_entry, Gtk.EntryIconPosition.SECONDARY,
                         "edit-clear", self.settings["calendar-icon-size"],
                         self.icons_path)

        vbox.pack_start(self.note_box, False, False, 0)
        self.note_box.pack_start(self.note_entry, True, True, 0)
        btn = Gtk.Button()
        btn.set_property("margin-top", 6)
        img = Gtk.Image()
        btn.set_image(img)
        update_image(img, "gtk-close", self.settings["calendar-icon-size"], self.icons_path)
        btn.set_tooltip_text("Cancel & close")
        btn.connect("clicked", self.cancel_close_popup)
        btn.set_always_show_image(True)
        self.note_box.pack_start(btn, False, False, 0)

        btn = Gtk.Button()
        btn.set_property("margin-top", 6)
        img = Gtk.Image()
        btn.set_image(img)
        update_image(img, "object-select", self.settings["calendar-icon-size"], self.icons_path)
        btn.set_tooltip_text("Save & close")
        btn.connect("clicked", self.apply_close_popup)
        btn.set_always_show_image(True)
        self.note_box.pack_start(btn, False, False, 0)

        self.popup.set_size_request(self.popup.get_allocated_width() * 2, 0)

        y, m, d = self.cal.get_date()
        if self.has_note(y, m, d):
            self.cal.select_day(d)

    def mark_days(self, *args):
        for i in range(1, 32):
            self.cal.unmark_day(i)
        y, m, d = self.cal.get_date()
        y, m, d = str(y), str(m), str(d)
        if y in self.calendar and m in self.calendar[y]:
            for i in range(1, 32):
                if str(i) in self.calendar[y][m]:
                    self.cal.mark_day(i)

    def has_note(self, year, month, day):
        y = str(year)
        m = str(month)
        d = str(day)
        if y in self.calendar and m in self.calendar[y] and d in self.calendar[y][m] and self.calendar[y][m][d]:
            return True

        return False

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
        save_json(c, self.path)
        self.popup.destroy()

    def load_calendar(self):
        if self.settings["calendar-path"]:
            self.path = self.settings["calendar-path"]
            c = load_json(self.path)
            if c is not None:
                self.calendar = c
                return True
            else:
                result = save_json(self.calendar, self.path)
                if result == "ok":
                    print("Created new calendar file at '{}'".format(self.path))
                    return True
                else:
                    eprint("Couldn't create '{}': {}. Using default path.".format(self.path, result))

        self.path = os.path.join(local_dir(), "calendar.json")
        c = load_json(self.path)
        if c is not None:
            self.calendar = c
        else:
            result = save_json(self.calendar, self.path)
            if result == "ok":
                print("Created new calendar file at '{}'".format(self.path))
                return True
            else:
                eprint("Couldn't create '{}': {}. No more idea...".format(self.path, result))

        return True

    def reload_calendar(self):
        if not self.popup or not self.popup.is_visible():
            self.load_calendar()

    def handle_keyboard(self, win, event):
        if event.type == Gdk.EventType.KEY_RELEASE and event.keyval == Gdk.KEY_Escape:
            self.popup.destroy()

    def on_day_selected(self, cal):
        y, m, d = cal.get_date()
        y, m, d = str(y), str(m), str(d)
        if y in self.calendar and m in self.calendar[y] and d in self.calendar[y][m]:
            self.note_entry.set_text(self.calendar[y][m][d])
        else:
            self.note_entry.set_text("")

        self.note_entry.set_icon_sensitive(Gtk.EntryIconPosition.SECONDARY, self.note_entry.get_text())
        self.note_box.show_all()

    def on_note_changed(self, eb):
        y, m, d = self.cal.get_date()
        y, m, d = str(y), str(m), str(d)
        if y not in self.calendar:
            self.calendar[y] = {}
        if m not in self.calendar[y]:
            self.calendar[y][m] = {}
        note = eb.get_text()
        if note:
            self.note_entry.set_icon_sensitive(Gtk.EntryIconPosition.SECONDARY, True)
            self.calendar[y][m][d] = eb.get_text()
        elif d in self.calendar[y][m]:
            self.note_entry.set_icon_sensitive(Gtk.EntryIconPosition.SECONDARY, False)
            self.calendar[y][m].pop(d, None)

    def on_note_icon_click(self, entry, icon, event):
        entry.set_text("")
