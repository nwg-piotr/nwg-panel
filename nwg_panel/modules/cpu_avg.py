#!/usr/bin/env python3

from gi.repository import GLib

import threading
import psutil

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk


class CpuAvg(Gtk.EventBox):
    def __init__(self):
        self.avg = 0
        self.cnt = 0
        Gtk.EventBox.__init__(self)
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(self.box)
        self.label = Gtk.Label()
        self.set_property("name", "executor")

        self.build_box()

        Gdk.threads_add_timeout_seconds(GLib.PRIORITY_LOW, 2, self.refresh)

    def update_widget(self, val, cnt):
        self.label.set_text(val)
        self.label.set_tooltip_text("{} checks".format(cnt))

        return False

    def get_output(self):
        try:
            val = psutil.cpu_percent(interval=1)
            self.avg = self.avg + val
            self.cnt += 1
            val = "{:.2f}%".format(round(self.avg / self.cnt, 2))
            GLib.idle_add(self.update_widget, val, str(self.cnt))
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
