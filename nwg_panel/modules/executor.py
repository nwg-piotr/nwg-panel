#!/usr/bin/env python3

import os
import subprocess
import signal

import gi
from gi.repository import GLib

from nwg_panel.tools import check_key, update_image, create_background_task, cmd_through_compositor

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk


class Executor(Gtk.EventBox):
    def __init__(self, settings, icons_path, executor_name):
        self.name = executor_name
        self.settings = settings
        self.icons_path = icons_path
        Gtk.EventBox.__init__(self)
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(self.box)
        self.image = Gtk.Image()
        self.label = Gtk.Label.new("")
        self.icon_path = None

        check_key(settings, "script", "")
        check_key(settings, "interval", 0)
        check_key(settings, "root-css-name", "root-executor")
        check_key(settings, "css-name", "")
        check_key(settings, "icon-placement", "left")
        check_key(settings, "icon-size", 16)
        check_key(settings, "tooltip-text", "")
        check_key(settings, "on-left-click", "")
        check_key(settings, "on-right-click", "")
        check_key(settings, "on-middle-click", "")
        check_key(settings, "on-scroll-up", "")
        check_key(settings, "on-scroll-down", "")
        check_key(settings, "angle", 0.0)
        check_key(settings, "sigrt", signal.SIGRTMIN)
        check_key(settings, "use-sigrt", False)

        self.label.set_angle(settings["angle"])

        # refresh signal in range SIGRTMIN+1 - SIGRTMAX
        self.sigrt = settings["sigrt"]
        self.use_sigrt = settings["use-sigrt"]

        if settings["angle"] != 0.0:
            self.box.set_orientation(Gtk.Orientation.VERTICAL)

        update_image(self.image, "view-refresh-symbolic", self.settings["icon-size"], self.icons_path)

        self.set_property("name", settings["root-css-name"])

        # reverting #57, as check_key only adds keys if MISSING, not if empty
        if settings["css-name"]:
            self.label.set_property("name", settings["css-name"])
        else:
            self.label.set_property("name", "executor-label")

        if settings["tooltip-text"]:
            self.set_tooltip_text(settings["tooltip-text"])

        if settings["on-left-click"] or settings["on-right-click"] or settings["on-middle-click"] or settings[
            "on-scroll-up"] or settings["on-scroll-down"]:
            self.connect('button-release-event', self.on_button_release)
            self.add_events(Gdk.EventMask.SCROLL_MASK)
            self.connect('scroll-event', self.on_scroll)

            self.connect('enter-notify-event', self.on_enter_notify_event)
            self.connect('leave-notify-event', self.on_leave_notify_event)

        self.build_box()
        self.refresh()

    def update_widget(self, output):
        # parse output
        label = new_path = None
        if output:
            output = [o.strip() for o in output]
            if len(output) == 1:
                if os.path.splitext(output[0])[1] in ('.svg', '.png'):
                    new_path = output[0]
                else:
                    label = output[0]
            elif len(output) == 2:
                new_path, label = output

        # update widget contents
        if new_path and new_path != self.icon_path:
            try:
                update_image(self.image,
                             new_path,
                             self.settings["icon-size"],
                             self.icons_path,
                             fallback=False)
                self.icon_path = new_path
            except:
                print("Failed setting image from {}".format(new_path))
                new_path = None

        if label:
            self.label.set_markup(label)

        # update widget visibility
        if new_path:
            if not self.image.get_visible():
                self.image.show()
        else:
            if self.image.get_visible():
                self.image.hide()

        if label:
            if not self.label.get_visible():
                self.label.show()
        else:
            if self.label.get_visible():
                self.label.hide()

        return False

    def get_output(self):
        if "script" in self.settings and self.settings["script"]:
            try:
                output = subprocess.check_output(self.settings["script"].split()).decode("utf-8").splitlines()
                GLib.idle_add(self.update_widget, output)
            except Exception as e:
                print(e)

    def refresh(self):
        thread = create_background_task(self.get_output, self.settings["interval"])
        thread.start()

    def build_box(self):
        if self.settings["icon-placement"] == "left":
            self.box.pack_start(self.image, False, False, 2)
        self.box.pack_start(self.label, False, False, 2)
        if self.settings["icon-placement"] != "left":
            self.box.pack_start(self.image, False, False, 2)

    def on_enter_notify_event(self, widget, event):
        widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
        widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)

    def on_leave_notify_event(self, widget, event):
        widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
        widget.unset_state_flags(Gtk.StateFlags.SELECTED)

    def on_button_release(self, widget, event):
        if event.button == 1 and self.settings["on-left-click"]:
            self.launch(self.settings["on-left-click"])
        elif event.button == 2 and self.settings["on-middle-click"]:
            self.launch(self.settings["on-middle-click"])
        elif event.button == 3 and self.settings["on-right-click"]:
            self.launch(self.settings["on-right-click"])

    def on_scroll(self, widget, event):
        if event.direction == Gdk.ScrollDirection.UP and self.settings["on-scroll-up"]:
            self.launch(self.settings["on-scroll-up"])
        elif event.direction == Gdk.ScrollDirection.DOWN and self.settings["on-scroll-down"]:
            self.launch(self.settings["on-scroll-down"])
        else:
            print("No command assigned")

    def launch(self, cmd):
        cmd = cmd_through_compositor(cmd)

        print(f"Executing: {cmd}")
        subprocess.Popen('{}'.format(cmd), shell=True)
