#!/usr/bin/env python3

import json

from gi.repository import Gtk, Gdk

from nwg_panel.tools import niri_ipc, update_image, update_image_fallback_desktop


class NiriTaskbar(Gtk.Box):
    def __init__(self, settings, position, outputs, workspaces, windows, focused_window, display_name="", icons_path=""):
        defaults = {
            "name-max-len": 24,
            "icon-size": 16,
            "workspaces-spacing": 0,
            "client-padding": 0,
            "show-app-icon": True,
            "show-app-name": True,
            "show-layout": True,
            "all-outputs": False,
            "angle": 0.0
        }
        for key in defaults:
            if key not in settings:
                settings[key] = defaults[key]
        self.settings = settings

        self.position = position
        self.display_name = display_name
        self.icons_path = icons_path

        self.outputs = None
        self.active_workspaces = []
        self.windows = None
        self.ws_nums = None
        self.workspaces = [None]
        self.focused_window = None

        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=settings["workspaces-spacing"])
        if self.settings["angle"] != 0.0:
            self.set_orientation(Gtk.Orientation.VERTICAL)

        self.refresh(outputs, workspaces, windows, focused_window)

    def parse_outputs(self, outputs):
        self.outputs = outputs

    def parse_workspaces(self, ws):
        self.ws_nums = []
        self.workspaces = {}
        self.active_workspaces = []
        for item in ws:
            self.ws_nums.append(item["id"])
            self.workspaces[item["id"]] = item
            if item["is_active"]:
                self.active_workspaces.append(item["id"])
        self.ws_nums.sort()

    def refresh(self, outputs, workspaces, windows, focused_window):
        self.outputs = outputs
        self.parse_workspaces(workspaces)
        self.windows = windows
        self.focused_window = focused_window
        for item in self.get_children():
            item.destroy()
        self.build_box()

    def build_box(self):
        for ws_num in self.ws_nums:
            ws_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
            if self.settings["angle"] != 0.0:
                ws_box.set_orientation(Gtk.Orientation.VERTICAL)
            self.pack_start(ws_box, False, False, 0)
            if self.workspaces[ws_num]["output"] == self.display_name or self.settings["all-outputs"]:
                eb = Gtk.EventBox()

                ws_box.pack_start(eb, False, False, 6)
                lbl = Gtk.Label()
                if ws_num in self.active_workspaces:
                    lbl.set_markup("<u>{}</u>:".format(self.workspaces[ws_num]["id"]))
                else:
                    lbl.set_text("{}:".format(self.workspaces[ws_num]["id"]))
                eb.add(lbl)
                win_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
                ws_box.pack_start(win_box, False, False, 0)
                for window in self.windows:
                    # if client["title"] prevents from creation of ghost client boxes
                    if window["title"] and window["workspace_id"] == ws_num:
                        client_box = ClientBox(self.settings, window, self.position, self.icons_path)
                        if self.focused_window and window["id"] == self.focused_window["id"]:
                            client_box.box.set_property("name", "task-box-focused")
                        else:
                            client_box.box.set_property("name", "task-box")
                        win_box.pack_start(client_box, False, False, self.settings["client-padding"])

        self.show_all()

    def on_ws_click(self, widget, event, ws_num):
        hyprctl("dispatch workspace name:{}".format(ws_num))


def on_enter_notify_event(widget, event):
    widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
    widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)


def on_leave_notify_event(widget, event):
    widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
    widget.unset_state_flags(Gtk.StateFlags.SELECTED)


class ClientBox(Gtk.EventBox):
    def __init__(self, settings, window, position, icons_path):
        self.position = position
        self.settings = settings
        self.id = window["id"]
        self.pid = window["pid"]
        self.icons_path = icons_path
        Gtk.EventBox.__init__(self)
        self.box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, spacing=0)
        if settings["angle"] != 0.0:
            self.box.set_orientation(Gtk.Orientation.VERTICAL)
        self.add(self.box)

        self.connect('enter-notify-event', on_enter_notify_event)
        self.connect('leave-notify-event', on_leave_notify_event)
        self.connect('button-release-event', self.on_click, window, self.box)

        image = None
        if settings["show-app-icon"]:
            name = window["app_id"]
            image = Gtk.Image()
            image.set_property("name", "task-box-icon")
            update_image_fallback_desktop(image, name, settings["image-size"], icons_path)
            self.box.pack_start(image, False, False, 4)

        name = window["title"][:settings["name-max-len"]]

        if settings["show-app-name"]:
            lbl = Gtk.Label()
            lbl.set_angle(self.settings["angle"])

            lbl.set_text(name)
            self.box.pack_start(lbl, False, False, 6)

            if name and image:
                image.set_tooltip_text(name)


        if settings["show-layout"]:
            if window["is_floating"]:
                img = Gtk.Image()
                update_image(img, "focus-windows", self.settings["image-size"], self.icons_path)
                self.box.pack_start(img, False, False, 0)

    def on_click(self, widget, event, client, popup_at_widget):
        if event.button == 1:
            command = {"Action":{"FocusWindow":{"id":client["id"]}}}
            niri_ipc(json.dumps(command), is_json=True)

        if event.button == 3:
            menu = self.context_menu(client)
            menu.show_all()
            if self.position == "bottom":
                menu.popup_at_widget(popup_at_widget, Gdk.Gravity.SOUTH, Gdk.Gravity.NORTH, None)
            else:
                menu.popup_at_widget(popup_at_widget, Gdk.Gravity.NORTH, Gdk.Gravity.SOUTH, None)

    def context_menu(self, client):
        menu = Gtk.Menu()
        menu.set_reserve_toggle_size(False)

        # Toggle floating
        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        img = Gtk.Image()
        update_image(img, "view-paged-symbolic", 16, self.icons_path)
        hbox.pack_start(img, True, True, 0)
        img = Gtk.Image()
        update_image(img, "view-dual-symbolic", 16, self.icons_path)
        hbox.pack_start(img, True, True, 0)
        item = Gtk.MenuItem()
        item.add(hbox)
        item.connect("activate", self.toggle_floating)
        item.set_tooltip_text("togglefloating")
        menu.append(item)

        # Fullscreen
        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        img = Gtk.Image()
        update_image(img, "view-fullscreen", 16, self.icons_path)
        hbox.pack_start(img, True, True, 0)
        item = Gtk.MenuItem()
        item.add(hbox)
        item.connect("activate", self.fullscreen)
        item.set_tooltip_text("fullscreen")
        menu.append(item)

        # Close
        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        img = Gtk.Image()
        update_image(img, "window-close", 16, self.icons_path)
        hbox.pack_start(img, True, True, 0)
        item = Gtk.MenuItem()
        item.add(hbox)
        item.connect("activate", self.close)
        item.set_tooltip_text("closewindow")
        menu.append(item)

        return menu

    def close(self, *args):
        command = {"Action": {"CloseWindow": {"id": self.id}}}
        niri_ipc(json.dumps(command), is_json=True)

    def toggle_floating(self, *args):
        command = {"Action":{"ToggleWindowFloating":{"id":self.id}}}
        niri_ipc(json.dumps(command), is_json=True)

    def fullscreen(self, *args):
        command = {"Action": {"FullscreenWindow": {"id": self.id}}}
        niri_ipc(json.dumps(command), is_json=True)

    def movetoworkspace(self, menuitem, ws_num):
        hyprctl("dispatch movetoworkspace {},address:{}".format(ws_num, self.address))
