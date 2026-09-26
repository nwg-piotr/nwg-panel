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


def on_monitor_clicked(widget, event, monitor_name):
    if event.button == 1:
        cmd = f"dispatch focusmon,{monitor_name}"
        get_mango_ipc(cmd)

def on_tag_clicked(widget, event, tag_index, monitor_name):
    if event.button == 1:
        cmd = f"dispatch viewcrossmon,{tag_index},{monitor_name}"
        get_mango_ipc(cmd)


def on_client_clicked(widget, event, client_id):
    if event.button == 1:
        cmd = f"dispatch focusid client,{client_id}"
        get_mango_ipc(cmd)


def on_scratchpad_client_clicked(widget, event, client_id):
    if event.button == 1:
        cmd = f"dispatch toggle_scratchpad"
    elif event.button == 3:
        cmd = f"dispatch focusid client,{client_id}"
    else:
        cmd = ""

    get_mango_ipc(cmd)


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
            "show-tags-from-all-monitors": True,   # determines if to show all displays->workspaces, or just the current display
            "sort-monitors-by-x": True,                  # outputs may be sorted by their x coordinate or alphabetically
            "show-per-tag-app-icons": False,             # determines if to show window icons for each workspace
            "show-empty-tags": True,
            "show-layout": True,
            "show-icon": True,                          # determines if to show per-tag window client icons
            "icon-size": 16,                            # client window icon size
            "show-name": True,                          # determines if to show active window title
            "name-length": 20,                          # limits active window title length
            "scratchpad-label": "Scr:",
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
            # monitor name label
            if self.settings["show-tags-from-all-monitors"]:
                eb_mon = Gtk.EventBox()
                eb_mon.connect("button-release-event", on_monitor_clicked, m_name)
                eb_mon.connect("enter_notify_event", on_enter_notify_event)
                eb_mon.connect("leave_notify_event", on_leave_notify_event)
                eb_mon.set_property("name", "mango-tags-output-box")
                self.pack_start(eb_mon, False, False, 6)

                lbl = Gtk.Label.new()
                lbl.set_markup(f"<b>{m_name}:</b>")
                if self.settings["angle"] != 0.0:
                    lbl.set_angle(self.settings["angle"])
                lbl.set_property("name", "mango-tags-output-name")
                eb_mon.add(lbl)

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
                            # build event box with tag index inside
                            eb = Gtk.EventBox()
                            eb.connect("enter_notify_event", on_enter_notify_event)
                            eb.connect("leave_notify_event", on_leave_notify_event)
                            eb.connect("button-release-event", on_tag_clicked, i["index"], m_name)

                            if i['is_active']:
                                eb.set_property("name", "task-box-focused")
                            else:
                                eb.set_property("name", "")

                            # Pakujemy tylko raz, po skonfigurowaniu właściwości
                            self.pack_start(eb, False, False, 3)

                            # tag index label
                            lbl = Gtk.Label.new(f"{i['index']}")
                            lbl.set_property("name", "mango-tag-index")
                            if self.settings["angle"] != 0.0:
                                lbl.set_angle(self.settings["angle"])
                            eb.add(lbl)

                            for client in self.all_clients:
                                # filter out clients in scratchpad
                                if client.get("is_scratchpad") or client.get("is_namedscratchpad"):
                                    continue

                                if client["monitor"] == m_name and i["index"] in client["tags"]:
                                    # client icon and title
                                    eb_icon_title = Gtk.EventBox()
                                    eb_icon_title.set_tooltip_text(client["title"])
                                    eb_icon_title.connect("button-release-event", on_client_clicked, client["id"])
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

                                        inner_box.pack_start(lbl, False, False, 0)

            scratchpad_clients = [
                c for c in self.all_clients
                if c["monitor"] == m_name and (c.get("is_scratchpad") or c.get("is_namedscratchpad"))
            ]

            if scratchpad_clients:
                # scratchpad label
                lbl = Gtk.Label.new(self.settings["scratchpad-label"])
                self.pack_start(lbl, False, False, 3)

                drawer_eb = Gtk.EventBox()
                drawer_eb.set_property("name", "mango-scratchpad-drawer")
                drawer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                drawer_eb.add(drawer_box)
                self.pack_start(drawer_eb, False, False, 6)

                for client in scratchpad_clients:
                    eb_icon_title = Gtk.EventBox()
                    eb_icon_title.set_tooltip_text(client["title"])
                    eb_icon_title.connect("button-release-event", on_client_clicked, client["id"])

                    # client icon
                    if self.settings["show-icon"]:
                        icon = Gtk.Image()
                        icon.set_property("name", "mango-app-icon")
                        try:
                            update_image_fallback_desktop(
                                icon, client["appid"], self.settings["icon-size"], self.icons_path,
                                fallback=False
                            )
                            eb_icon_title.add(icon)
                        except Exception as e:
                            eprint(f"MangoTags:Scratchpad could not update per-ws icon for appid '{client['appid']}'", e)

                        drawer_box.pack_start(eb_icon_title, False, False, 3)

        self.show_all()
