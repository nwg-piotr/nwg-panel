#!/usr/bin/env python3

import os
import subprocess
import signal
import threading

import gi
from gi.repository import GLib

from nwg_panel.tools import check_key, update_image, create_background_task, cmd_through_compositor

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
        self.label = Gtk.Label.new("")
        self.icon_path = None
        self.icon_mtime = None
        self.dynamic_tooltip = False
        self.loop_started = False
        self.run_lock = threading.Lock()
        self.rerun_pending = False  # a refresh requested while the script was running
        self.tooltip_image_path = None
        self.tooltip_image_key = None
        self.tooltip_box = None

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
            else:
                # 3+ lines: icon path (may be empty), label, then a tooltip (Pango markup, may span several lines)
                new_path, label = output[0], output[1]
                tip = output[2:]
                # optional image on top of the tooltip: 1st tooltip line = path to a .svg / .png file
                if os.path.splitext(tip[0])[1] in ('.svg', '.png') and os.path.isfile(tip[0]):
                    self.set_tooltip_image(tip[0])
                    tip = tip[1:]
                else:
                    self.set_tooltip_image(None)
                self.set_tooltip_markup("\n".join(tip) or " ")
                self.dynamic_tooltip = True

        if self.dynamic_tooltip and (not output or len(output) < 3):
            # the script stopped providing a tooltip: restore the static one (if any)
            self.set_tooltip_image(None)
            self.set_tooltip_text(self.settings["tooltip-text"] or None)
            self.dynamic_tooltip = False

        # update widget contents
        # A script may rewrite the same image file on each run (e.g. a generated graph):
        # reload it when the path OR the file modification time changed.
        new_mtime = None
        if new_path:
            try:
                new_mtime = os.path.getmtime(new_path)
            except OSError:
                pass  # icon name, not a file
        if new_path and (new_path != self.icon_path or new_mtime != self.icon_mtime):
            try:
                update_image(self.image,
                             new_path,
                             self.settings["icon-size"],
                             self.icons_path,
                             fallback=False)
                self.icon_path = new_path
                self.icon_mtime = new_mtime
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

    def set_tooltip_image(self, path):
        if path and self.tooltip_box is None:
            # built once, on first use: image above the Pango markup
            self.tooltip_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            self.tooltip_img = Gtk.Image()
            self.tooltip_img.set_halign(Gtk.Align.START)
            self.tooltip_lbl = Gtk.Label()
            self.tooltip_lbl.set_xalign(0)
            self.tooltip_box.pack_start(self.tooltip_img, False, False, 0)
            self.tooltip_box.pack_start(self.tooltip_lbl, False, False, 0)
            self.tooltip_box.show_all()
            self.connect("query-tooltip", self.on_query_tooltip)
        self.tooltip_image_path = path

    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        path = self.tooltip_image_path
        if not path:
            return False  # default markup tooltip
        try:
            key = (path, os.path.getmtime(path))
            if key != self.tooltip_image_key:  # reload only when the file changed
                self.tooltip_img.set_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file(path))
                self.tooltip_image_key = key
        except Exception as e:
            print("Failed loading tooltip image {}: {}".format(path, e))
            return False
        markup = (self.get_tooltip_markup() or "").strip()
        self.tooltip_lbl.set_markup(markup)
        self.tooltip_lbl.set_visible(bool(markup))
        tooltip.set_custom(self.tooltip_box)
        return True

    def get_output(self):
        if "script" in self.settings and self.settings["script"]:
            # serialize runs: a signal-triggered refresh must not overlap the periodic one. Requests that
            # arrive while the script runs are merged into one rerun instead of piling up threads behind the lock.
            if not self.run_lock.acquire(blocking=False):
                self.rerun_pending = True
                return
            try:
                # a script that never returns used to hold the lock (and a thread) forever
                timeout = max(self.settings["interval"], 30) if self.settings["interval"] > 0 else 60
                output = subprocess.check_output(self.settings["script"].split(), timeout=timeout) \
                    .decode("utf-8", errors="replace").splitlines()
                GLib.idle_add(self.update_widget, output)
            except subprocess.TimeoutExpired:
                print("Executor '{}': script timed out after {} s".format(self.name, timeout))
            except Exception as e:
                print(e)
            finally:
                self.run_lock.release()
            if self.rerun_pending:
                self.rerun_pending = False
                self.get_output()

    def refresh(self):
        # The periodic loop is started once; later calls (RT signal) run the script once.
        # Starting a new loop on each call would multiply the script executions (#67).
        if self.loop_started:
            thread = create_background_task(self.get_output, 0)
        else:
            self.loop_started = True
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
