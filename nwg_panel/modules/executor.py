#!/usr/bin/env python3

from gi.repository import GLib

import subprocess

import threading


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

        # We won't warn about these keys missing, so they need to be mentioned id README
        if "css-name" in settings:
            self.label.set_property("name", settings["css-name"])
        else:
            self.label.set_property("name", "executor-label")
        
        if "icon-size" not in self.settings:
            self.settings["icon-size"] = 16
        
        self.icon_path = None
        
        self.build_box()
        self.refresh()

        check_key(settings, "interval", 0)
        if settings["interval"] > 0:
            Gdk.threads_add_timeout_seconds(GLib.PRIORITY_LOW, settings["interval"], self.refresh)

    def update_widget(self, output):
        if len(output) == 1:
            if self.image.get_visible():
                self.image.hide()
            self.label.set_text(output[0].strip())
        elif len(output) == 2:
            new_path = output[0].strip()
            if new_path != self.icon_path:
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                        new_path, self.settings["icon-size"], self.settings["icon-size"])
                    self.image.set_from_pixbuf(pixbuf)
                    self.icon_path = new_path
                except:
                    print("Failed setting image from {}".format(output[0].strip()))
                if not self.image.get_visible():
                    self.image.show()
            
            self.label.set_text(output[1].strip())
        
        return False

    def get_output(self):
        if "script" in self.settings:
            try:
                output = subprocess.check_output(self.settings["script"].split()).decode("utf-8").splitlines()
                GLib.idle_add(self.update_widget, output)
            except Exception as e:
                print(e)
        
    def refresh(self):
        thread = threading.Thread(target=self.get_output)
        thread.daemon = True
        thread.start()
        return True

    def build_box(self):
        self.box.pack_start(self.image, False, False, 4)
        self.box.pack_start(self.label, False, False, 0)
        self.label.show()

