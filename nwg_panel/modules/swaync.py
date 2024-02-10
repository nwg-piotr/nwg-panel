#!/usr/bin/env python3

from gi.repository import GLib

import subprocess

from nwg_panel.tools import check_key, update_image, create_background_task, cmd_through_compositor

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk


class SwayNC(Gtk.EventBox):
    def __init__(self, settings, icons_path, panel_position):
        self.settings = settings
        self.icons_path = icons_path
        Gtk.EventBox.__init__(self)
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        if panel_position == "left" or panel_position == "right":
            self.box.set_orientation(Gtk.Orientation.VERTICAL)
        self.add(self.box)
        self.image = Gtk.Image()
        self.label = Gtk.Label()
        self.icon_path = None

        check_key(settings, "interval", 1)
        check_key(settings, "root-css-name", "root-executor")
        check_key(settings, "css-name", "executor-label")
        check_key(settings, "icon-placement", "left")
        check_key(settings, "icon-size", 18)
        check_key(settings, "tooltip-text", "")
        check_key(settings, "on-left-click", "swaync-client -t")
        check_key(settings, "on-right-click", "")
        check_key(settings, "on-middle-click", "")
        check_key(settings, "on-scroll-up", "")
        check_key(settings, "on-scroll-down", "")
        check_key(settings, "always-show-icon", True)

        update_image(self.image, "view-refresh-symbolic", self.settings["icon-size"], self.icons_path)

        self.set_property("name", settings["root-css-name"])

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
        if output:
            try:
                num = int(output)
                if num > 0 or self.settings["always-show-icon"]:
                    if not self.icon_path == "bell":
                        update_image(self.image, "bell", self.settings["icon-size"], self.icons_path)
                        self.icon_path = "bell"
                    self.image.show()
                else:
                    self.image.hide()

                if num > 0:
                    self.label.set_text(str(num))
                    self.label.show()
                else:
                    self.label.hide()
            except:
                update_image(self.image, "view-refresh-symbolic", self.settings["icon-size"], self.icons_path)
                self.icon_path = "view-refresh-symbolic"
                self.image.show()

        return False

    def get_output(self):
        try:
            output = subprocess.check_output("swaync-client -c".split()).decode("utf-8")
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
        elif event.direction == Gdk.ScrollDirection.DOWN and self.settings["on-scroll-up"]:
            self.launch(self.settings["on-scroll-up"])
        else:
            print("No command assigned")

    def launch(self, cmd):
        cmd = cmd_through_compositor(cmd)

        print(f"Executing: {cmd}")
        subprocess.Popen('{}'.format(cmd), shell=True)
