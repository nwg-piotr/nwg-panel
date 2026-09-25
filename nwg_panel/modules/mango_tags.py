#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

from nwg_panel.tools import (eprint, update_image_fallback_desktop)
from nwg_panel.mango_ipc import get_mango_ipc

import json


def on_enter_notify_event(widget, event):
    widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
    widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)


def on_leave_notify_event(widget, event):
    widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
    widget.unset_state_flags(Gtk.StateFlags.SELECTED)


class MangoTags(Gtk.Box):
    def __init__(self, settings, panel_output, icons_path):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        self.set_property("name", "mango-tags")

        # passed values
        self.settings = settings
        self.icons_path = icons_path
        self.output_name = panel_output

        # obtained in refresh()
        self.all_monitors = None            # list of dicts
        self.sorted_monitor_names = None    # list of strings
        self.all_tags = None                # list of dicts
        self.all_clients = None             # list of dicts

        # default settings
        defaults = {
            "show-tags-from-all-monitors": False,   # determines if to show all displays->workspaces, or just the current display
            "sort-monitors-by-x": True,                  # outputs may be sorted by their x coordinate or alphabetically
            "show-per-tag-app-icons": False,             # determines if to show window icons for each workspace
            "show-empty-tags": False,
            "show-layout": True,
            "show-icon": True,                          # determines if to show active window icon
            "icon-size": 16,                            # active window icon size
            "show-name": True,                          # determines if to show active window title
            "name-length": 20,                          # limits active window title length
            "angle": 0.0                                # use 90 or 270 for vertical panels
        }
        for key in defaults:
            if key not in self.settings:
                self.settings[key] = defaults[key]

        if self.settings["angle"] != 0.0:
            self.set_orientation(Gtk.Orientation.VERTICAL)

    def refresh(self, all_monitors=None, all_tags=None, all_clients=None):
        # extract lists from one item long dictionaries
        self.all_monitors = all_monitors["monitors"]
        self.all_tags = all_tags["all_tags"]
        self.all_clients = all_clients["clients"]

        if self.settings["sort-monitors-by-x"]:
            # sort monitor names by monitor x coordinate
            sorted_monitors = sorted(self.all_monitors, key=lambda monitor: monitor['x'])
        else:
            # sort monitor names alphabetically
            sorted_monitors = sorted(self.all_monitors, key=lambda name: name['name'])

        # build class-level sorted monitors list
        self.sorted_monitor_names = []
        for item in sorted_monitors:
            self.sorted_monitor_names.append(item["name"])

        self.build_box()

    def build_box(self):
        # clear old content
        for child in self.get_children():
            self.remove(child)

        # limit output to current monitor if set by the user
        if not self.settings["show-tags-from-all-monitors"]:
            self.sorted_monitor_names = [self.output_name]

        for m_name in self.sorted_monitor_names:
            print(f"{m_name}:", end=" ")
            # monitor name label
            if self.settings["show-tags-from-all-monitors"]:
                lbl = Gtk.Label.new(f"{m_name}:")
                if self.settings["angle"] != 0.0:
                    lbl.set_angle(self.settings["angle"])
                lbl.set_property("name", "mango-tags-output-name")
                self.pack_start(lbl, False, False, 6)

            if self.settings["show-layout"]:
                for _i in self.all_monitors:
                    if m_name == _i["name"]:
                        lbl = Gtk.Label.new(_i["layout_symbol"])
                        if self.settings["angle"] != 0.0:
                            lbl.set_angle(self.settings["angle"])
                        lbl.set_property("name", "mango-tags-layout-symbol")
                        self.pack_start(lbl, False, False, 6)

            for item in self.all_tags:
                if item["monitor"] == m_name:
                    for i in item["tags"]:
                        # show if "show-empty-tags" demanded or is_active or has some clients
                        if self.settings["show-empty-tags"] or i["is_active"] or i.get("client_count", 0) > 0:
                            print(i["index"], end=" ")
                            # build event box with tag index inside
                            eb = Gtk.EventBox()
                            eb.connect("enter_notify_event", on_enter_notify_event)
                            eb.connect("leave_notify_event", on_leave_notify_event)
                            # eb.connect("button-release-event", on_workspace_clicked, item["id"])
                            self.pack_start(eb, False, False, 3)

                            if i['is_active']:
                                eb.set_property("name", "task-box-focused")
                            else:
                                eb.set_property("name", "")
                            self.pack_start(eb, False, False, 3)

                            # tag index label
                            lbl = Gtk.Label.new(f"{i["index"]}")
                            lbl.set_property("name", "mango-tag-index")
                            if self.settings["angle"] != 0.0:
                                lbl.set_angle(self.settings["angle"])
                            eb.add(lbl)

                            for client in self.all_clients:
                                if client["monitor"] == m_name and i["index"] in client["tags"]:
                                    print(client["appid"], end=" ")
                                    # client icon and title
                                    eb_icon_title = Gtk.EventBox()
                                    eb_icon_title.set_tooltip_text(client["title"])

                                    # TWORZYMY WEWNĘTRZNY KONTENER
                                    inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                                    eb_icon_title.add(inner_box)

                                    if self.settings["show-icon"] or self.settings["show-name"]:
                                        self.pack_start(eb_icon_title, False, False, 3)

                                    # icon
                                    if self.settings["show-icon"]:
                                        icon = Gtk.Image()
                                        icon.set_property("name", "mango-app-icon")
                                        try:
                                            update_image_fallback_desktop(
                                                icon, client["appid"], self.settings["icon-size"], self.icons_path,
                                                fallback=False
                                            )
                                            # Pakujemy ikonę do wewnętrznego boxa!
                                            inner_box.pack_start(icon, False, False, 0)
                                        except:
                                            eprint(
                                                f"MangoTags: could not update per-ws icon for appid '{client['appid']}'")

                                    # title
                                    if self.settings["show-name"]:
                                        max_len = self.settings["name-length"]
                                        display_title = client['title'] if len(client['title']) <= max_len else f"{client['title'][:max_len]}…"
                                        lbl = Gtk.Label.new(f"{display_title}")
                                        lbl.set_property("name", "mango-client-title")
                                        if self.settings["angle"] != 0.0:
                                            lbl.set_angle(self.settings["angle"])

                                        # Pakujemy tytuł do wewnętrznego boxa obok ikony!
                                        inner_box.pack_start(lbl, False, False, 0)

        print("\n")
        self.show_all()
