#!/usr/bin/env python3
import json

from gi.repository import Gtk, Gdk

import nwg_panel.common
from nwg_panel.tools import check_key, update_image, update_image_fallback_desktop, hyprctl


class HyprlandWorkspaces(Gtk.Box):
    def __init__(self, settings, icons_path):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.settings = settings
        self.num_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        self.ws_id2name = {}
        self.name_label = Gtk.Label()
        self.icon = Gtk.Image()
        self.layout_icon = Gtk.Image()
        self.icons_path = icons_path

        self.ws_nums = []

        self.build_box()
        self.refresh()

    def build_box(self):
        check_key(self.settings, "numbers", [])  # del
        check_key(self.settings, "custom-labels", [])  # del
        check_key(self.settings, "focused-labels", [])  # del
        check_key(self.settings, "num-ws", 10)  # new
        check_key(self.settings, "show-icon", True)
        check_key(self.settings, "image-size", 16)
        check_key(self.settings, "show-name", True)
        check_key(self.settings, "name-length", 40)
        check_key(self.settings, "mark-content", True)
        check_key(self.settings, "show-empty", True)
        check_key(self.settings, "show-names", True)
        check_key(self.settings, "show-layout", True)
        check_key(self.settings, "angle", 0.0)

        if self.settings["angle"] != 0.0:
            self.set_orientation(Gtk.Orientation.VERTICAL)
            self.num_box.set_orientation(Gtk.Orientation.VERTICAL)

        self.pack_start(self.num_box, False, False, 0)

        for i in range(1, self.settings["num-ws"] + 1):
            self.ws_nums.append(i)

        if self.settings["show-icon"]:
            self.pack_start(self.icon, False, False, 6)

        if self.settings["show-name"]:
            self.pack_start(self.name_label, False, False, 0)

        if self.settings["show-layout"]:
            self.pack_start(self.layout_icon, False, False, 6)

        self.show_all()
        update_image(self.layout_icon, "window-pop-out-symbolic", self.settings["image-size"], self.icons_path)
        self.layout_icon.hide()

    def build_number(self, num, add_dot=False):
        eb = Gtk.EventBox()
        eb.connect("enter_notify_event", self.on_enter_notify_event)
        eb.connect("leave_notify_event", self.on_leave_notify_event)
        eb.connect("button-release-event", self.on_click, num)
        eb.add_events(Gdk.EventMask.SCROLL_MASK)
        eb.connect('scroll-event', self.on_scroll)

        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        if self.settings["angle"] != 0.0:
            box.set_orientation(Gtk.Orientation.VERTICAL)
        eb.add(box)

        name = str(num)
        if self.settings["show-names"] and num in self.ws_id2name and self.ws_id2name[num] != str(num):
            name = "{} {}".format(num, self.ws_id2name[num])

        lbl = Gtk.Label.new("{}".format(name)) if not add_dot else Gtk.Label.new("{}.".format(name))
        lbl.set_use_markup(True)
        if self.settings["angle"] != 0.0:
            lbl.set_angle(self.settings["angle"])
            self.name_label.set_angle(self.settings["angle"])

        box.pack_start(lbl, False, False, 6)

        return eb, lbl

    def refresh(self):
        output = hyprctl("j/workspaces")
        workspaces = json.loads(output)
        occupied_workspaces = []
        self.ws_id2name = {}
        for ws in workspaces:
            if ws["id"] not in occupied_workspaces:
                occupied_workspaces.append(ws["id"])

            self.ws_id2name[ws["id"]] = ws["name"]
        occupied_workspaces.sort()

        output = hyprctl("j/activewindow")
        active_window = json.loads(output)

        if active_window:
            client_class = active_window["class"]
            client_title = active_window["title"][:self.settings["name-length"]]
            floating = active_window["floating"]
        else:
            client_class = ""
            client_title = ""
            floating = False

        if self.settings["show-icon"]:
            self.update_icon(client_class, client_title)
        if self.settings["show-name"]:
            self.name_label.set_text(client_title)
        if self.settings["show-layout"]:
            if floating:
                self.layout_icon.show()
            else:
                self.layout_icon.hide()

        for c in self.num_box.get_children():
            c.destroy()

        for num in self.ws_nums:
            if num in occupied_workspaces or self.settings["show-empty"]:
                dot = num in occupied_workspaces and self.settings["show-empty"]
                eb, lbl = self.build_number(num, dot)
                self.num_box.pack_start(eb, False, False, 0)
                self.num_box.show_all()

    def update_icon(self, client_class, client_title):
        loaded_icon = False
        if client_class and client_title:
            try:
                update_image_fallback_desktop(self.icon,
                                              client_class,
                                              self.settings["image-size"],
                                              self.icons_path,
                                              fallback=False)
                loaded_icon = True
                if not self.icon.get_visible():
                    self.icon.show()
            except:
                pass
        else:
            self.icon.hide()

        if not loaded_icon and self.icon.get_visible():
            self.icon.hide()

    def on_click(self, event_box, event_button, num):
        nwg_panel.common.i3.command("workspace number {}".format(num))

    def on_scroll(self, event_box, event):
        if event.direction == Gdk.ScrollDirection.UP:
            nwg_panel.common.i3.command("workspace prev")
        elif event.direction == Gdk.ScrollDirection.DOWN:
            nwg_panel.common.i3.command("workspace next")

    def on_enter_notify_event(self, widget, event):
        widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
        widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)

    def on_leave_notify_event(self, widget, event):
        widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
        widget.unset_state_flags(Gtk.StateFlags.SELECTED)
