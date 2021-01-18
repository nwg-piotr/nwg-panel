#!/usr/bin/env python3

from gi.repository import Gtk, GLib, GdkPixbuf

import sys
sys.path.append('../')

import os
import subprocess
from threading import Thread
from queue import Queue, Empty



import nwg_panel.common
from nwg_panel.tools import check_key

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk, GdkPixbuf


class Executor(Gtk.EventBox):
    def __init__(self, settings):
        self.settings = settings
        Gtk.EventBox.__init__(self)
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(self.box)
        self.image = Gtk.Image.new_from_icon_name("dialog-question", Gtk.IconSize.MENU)
        self.label = Gtk.Label("---")
        # We won't warn about this key missing, so it needs to be mentioned id README
        if "css-name" in settings:
            self.label.set_property("name", settings["css-name"])
        else:
            self.label.set_property("name", "executor-label")
        
        self.q = None
        self.ON_POSIX = 'posix' in sys.builtin_module_names
        
        self.build_box()
        self.refresh()

        check_key(settings, "interval", 0)
        if settings["interval"] > 0:
            print("Gonna refresh")
            Gdk.threads_add_timeout_seconds(GLib.PRIORITY_DEFAULT, settings["interval"], self.refresh)

    def enqueue_output(self, out, queue):
        lines = out.readlines()
        if len(lines) > 1:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(lines[0].decode('utf-8').strip(), 16, 16)
            self.image.set_from_pixbuf(pixbuf)
            self.image.show()
            self.label.set_text(lines[1].decode('utf-8').strip())
        else:
            self.image.hide()
            self.label.set_text(lines[0].decode('utf-8').strip())
        out.close()

    def build_box(self):
        self.box.pack_start(self.image, False, False, 4)
        self.box.pack_start(self.label, False, False, 0)
        self.label.show()
    
    def refresh(self):
        if "script" in self.settings:
            p = subprocess.Popen(self.settings["script"].split(), stdout=subprocess.PIPE, close_fds=self.ON_POSIX)
            self.q = Queue()
            t = Thread(target=self.enqueue_output, args=(p.stdout, self.q))
            t.daemon = True  # thread dies with the program
            t.start()
            
            return True

    def old_refresh(self):
        print("refreshing")
        self.script_output()
        try:
            line = self.q.get_nowait()  # or q.get(timeout=.1)
        except Empty:
            print('no output yet')
        else:
            print("line=", line)
        """if output[0]:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(output[0], 16, 16)
            self.image.set_from_pixbuf(pixbuf)
            self.image.show()
            self.label.set_text(output[1])
        else:
            self.image.hide()
            self.label.set_text(output[1])"""

        return True
