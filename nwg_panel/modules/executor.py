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
        self.box.set_property("name", "task-box")
        self.add(self.box)
        self.image = Gtk.Image.new_from_icon_name("wtf", Gtk.IconSize.MENU)
        self.label = Gtk.Label("")
        self.icon_path = None

        check_key(settings, "script", "")
        check_key(settings, "interval", 0)
        check_key(settings, "css-name", "")
        check_key(settings, "icon-size", 16)
        check_key(settings, "show-icon", True)
        check_key(settings, "tooltip-text", "")
        check_key(settings, "on-left-click", "")
        check_key(settings, "on-right-click", "")
        check_key(settings, "on-middle-click", "")
        check_key(settings, "on-scroll-up", "")
        check_key(settings, "on-scroll-down", "")

        if settings["css-name"]:
            self.label.set_property("name", settings["css-name"])
        else:
            self.label.set_property("name", "executor-label")

        if settings["tooltip-text"]:
            self.set_tooltip_text(settings["tooltip-text"])

        if settings["on-left-click"] or settings["on-right-click"] or settings["on-middle-click"] or settings[
                "on-scroll-up"] or settings["on-scroll-down"]:
            self.connect('button-press-event', self.on_button_press)
            self.add_events(Gdk.EventMask.SCROLL_MASK)
            self.connect('scroll-event', self.on_scroll)

            self.connect('enter-notify-event', self.on_enter_notify_event)
            self.connect('leave-notify-event', self.on_leave_notify_event)

        self.build_box()
        self.refresh()

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
        if "script" in self.settings and self.settings["script"]:
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
        self.box.pack_start(self.image, False, False, 2)
        self.box.pack_start(self.label, False, False, 2)
        self.label.show()

    def on_enter_notify_event(self, widget, event):
        self.get_style_context().set_state(Gtk.StateFlags.SELECTED)

    def on_leave_notify_event(self, widget, event):
        self.get_style_context().set_state(Gtk.StateFlags.NORMAL)

    def on_button_press(self, widget, event):
        if event.button == 3 and self.settings["on-left-click"]:
            self.launch(self.settings["on-left-click"])
        elif event.button == 2 and self.settings["on-middle-click"]:
            self.launch(self.settings["on-middle-click"])
        elif event.button == 1 and self.settings["on-right-click"]:
            self.launch(self.settings["on-right-click"])

    def on_scroll(self, widget, event):
        if event.direction == Gdk.ScrollDirection.UP and self.settings["on-scroll-up"]:
            self.launch(self.settings["on-scroll-up"])
        elif event.direction == Gdk.ScrollDirection.DOWN and self.settings["on-scroll-up"]:
            self.launch(self.settings["on-scroll-up"])
        else:
            print("No command assigned")

    def launch(self, cmd):
        print("Executing '{}'".format(cmd))
        subprocess.Popen('exec {}'.format(cmd), shell=True)
