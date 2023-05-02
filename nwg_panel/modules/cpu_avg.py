#!/usr/bin/env python3

from gi.repository import GLib

import psutil

import gi

from nwg_panel.tools import create_background_task

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
        self.label.set_property("name", "executor-label")

        self.build_box()
        self.refresh()

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
        thread = create_background_task(self.get_output, 2)
        thread.start()

    def build_box(self):
        self.box.pack_start(self.label, False, False, 4)
        self.label.show()
