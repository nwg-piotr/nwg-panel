#!/usr/bin/env python3

import subprocess
import threading
import signal

from shlex import split

import gi
from gi.repository import GLib

from nwg_panel.tools import check_key, update_image

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk, GdkPixbuf


class Executor(Gtk.EventBox):
    def __init__(self, settings, icons_path, executor_name):
        self.name = executor_name
        self.settings = settings
        self.icons_path = icons_path
        Gtk.EventBox.__init__(self)
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(self.box)
        self.image = Gtk.Image()
        self.label = Gtk.Label("")
        self.icon_path = None
        self.process = None

        check_key(settings, "script", "")
        check_key(settings, "interval", 0)
        check_key(settings, "icon", "view-refresh-symbolic")
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
        check_key(settings, "continuous", False)

        self.label.set_angle(settings["angle"])

        # refresh signal in range SIGRTMIN+1 - SIGRTMAX
        self.sigrt = settings["sigrt"]
        self.use_sigrt = settings["use-sigrt"]

        if settings["angle"] != 0.0:
            self.box.set_orientation(Gtk.Orientation.VERTICAL)

        if self.settings["icon"] is None or len(self.settings["icon"]) == 0:
            self.image.hide()
        else:
            update_image(self.image, self.settings["icon"], self.settings["icon-size"], self.icons_path)

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
        if output:
            if len(output) == 1:
                print("output1 {}".format(output))
                if output[0].endswith(".svg") or output[0].endswith(".png"):
                    new_path = output[0].strip()
                    if new_path != self.icon_path:
                        if "/" not in new_path and "." not in new_path:  # name given instead of path
                            update_image(self.image, new_path, self.settings["icon-size"], self.icons_path)
                            self.icon_path = new_path
                        else:
                            try:
                                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                                    new_path, self.settings["icon-size"], self.settings["icon-size"])
                                self.image.set_from_pixbuf(pixbuf)
                                self.icon_path = new_path
                            except:
                                print("Failed setting image from {}".format(output[0].strip()))
                            if not self.image.get_visible():
                                self.image.show()
                            if self.label.get_visible():
                                self.label.hide()
                else:
                    if self.image.get_visible():
                        self.image.hide()
                    self.label.set_text(output[0].strip())
                    if not self.label.get_visible():
                        self.label.show()

            elif len(output) == 2:
                new_path = output[0].strip()
                if new_path == "":
                    if self.image.get_visible():
                        self.image.hide()
                elif "/" not in new_path and "." not in new_path:  # name given instead of path
                    update_image(self.image, new_path, self.settings["icon-size"], self.icons_path)
                    self.icon_path = new_path
                else:
                    if new_path != self.icon_path:
                        try:
                            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                                new_path, self.settings["icon-size"], self.settings["icon-size"])
                            self.image.set_from_pixbuf(pixbuf)
                            self.icon_path = new_path
                        except:
                            print("Failed setting image from {}".format(output[0].strip()))

                self.label.set_text(output[1].strip())
                self.image.show()
                if self.label.get_text():
                    self.label.show()
        else:
            if self.image.get_visible():
                self.image.hide()
            if self.label.get_visible():
                self.label.hide()

        return False

    def get_output(self):
        if "script" in self.settings and self.settings["script"]:
            script = split(self.settings["script"])
            continuous = self.settings["continuous"]
            try:
                if not continuous:
                    subprocess.check_output(script)
                    output = subprocess.check_output(split(self.settings["script"])).decode("utf-8").splitlines()
                    GLib.idle_add(self.update_widget, output)
                    return

                if self.process is not None and self.process.poll() is None:
                    # Last process has not yet finished
                    # Wait for it, possibly this is a continuous output
                    return

                self.process = subprocess.Popen(script,
                                                stdout = subprocess.PIPE)
                first_line = None
                while True:
                    line = self.process.stdout.readline().decode('utf-8')
                    if line is None or len(line) == 0: break

                    if first_line is None:
                        first_line = line
                    else:
                        GLib.idle_add(self.update_widget, [first_line, line])
                        first_line = None
            except Exception as e:
                print(e)

    def refresh(self):
        thread = threading.Thread(target=self.get_output)
        thread.daemon = True
        thread.start()
        return True

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

    def on_button_press(self, widget, event):
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
        print("Executing '{}'".format(cmd))
        subprocess.Popen('exec {}'.format(cmd), shell=True)
