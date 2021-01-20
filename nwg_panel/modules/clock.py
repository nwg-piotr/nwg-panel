#!/usr/bin/env python3

from gi.repository import GLib

import subprocess
import threading
from datetime import datetime

from nwg_panel.tools import check_key

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk, GdkPixbuf


class Clock(Gtk.EventBox):
    def __init__(self, settings):
        self.settings = settings
        Gtk.EventBox.__init__(self)
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(self.box)
        self.label = Gtk.Label("")

        # We won't warn about these keys missing, so they need to be mentioned id README
        if "css-name" in settings:
            self.label.set_property("name", settings["css-name"])
        else:
            self.label.set_property("name", "executor-label")
            
        if "format" not in settings:
            self.settings["format"] = "%a, %d. %b  %H:%M:%S"

        self.build_box()
        self.refresh()

        check_key(settings, "interval", 1)
        if settings["interval"] > 0:
            Gdk.threads_add_timeout_seconds(GLib.PRIORITY_LOW, settings["interval"], self.refresh)

    def update_widget(self, output):
        self.label.set_text(output)

        return False

    def get_output(self):
        now = datetime.now()
        try:
            time = now.strftime(self.settings["format"])
            GLib.idle_add(self.update_widget, time)
        except Exception as e:
            print(e)

    def refresh(self):
        thread = threading.Thread(target=self.get_output)
        thread.daemon = True
        thread.start()
        return True

    def build_box(self):
        self.box.pack_start(self.label, False, False, 0)
        self.label.show()

