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
        self.image = Gtk.Image.new_from_icon_name("wtf", Gtk.IconSize.MENU)
        self.label = Gtk.Label("")
        # We won't warn about this key missing, so it needs to be mentioned id README
        if "css-name" in settings:
            self.label.set_property("name", settings["css-name"])
        else:
            self.label.set_property("name", "executor-label")
        self.icon_path = None
        
        self.build_box()
        self.refresh()

        check_key(settings, "interval", 0)
        if settings["interval"] > 0:
            Gdk.threads_add_timeout_seconds(GLib.PRIORITY_LOW, settings["interval"], self.refresh)
            #GLib.timeout_add(settings["interval"], self.refresh)

    def enqueue_output(self, out, queue):
        for line in iter(out.readline, b''):
            queue.put(line)
        out.close()

        # Depending on the executor, we expect 1 or 2 lines
        lines = []
        for i in range(2):
            try:
                line = queue.get_nowait()  # or q.get(timeout=.1)
                lines.append(line.decode("utf-8").strip())
            except Empty:
                pass
            
        if len(lines) > 1:
            if self.icon_path != lines[0]:  # update image only if changed

                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(lines[0], 16, 16)
                self.image.set_from_pixbuf(pixbuf)
                if not self.image.get_visible():
                    self.image.show()

                self.icon_path = lines[0]

            self.label.set_text(lines[1])
        else:
            if self.image.get_visible():
                self.image.hide()

            if self.label.get_text() != lines[0]:
                self.label.set_text(lines[0])

    def build_box(self):
        self.box.pack_start(self.image, False, False, 4)
        self.box.pack_start(self.label, False, False, 0)
        self.label.show()
    
    def refresh(self):
        if "script" in self.settings:
            ON_POSIX = 'posix' in sys.builtin_module_names
            p = subprocess.Popen(self.settings["script"].split(), stdout=subprocess.PIPE, close_fds=ON_POSIX)
            q = Queue()
            t = Thread(target=self.enqueue_output, args=(p.stdout, q))
            t.daemon = True  # thread dies with the program
            t.start()
            
            return True
