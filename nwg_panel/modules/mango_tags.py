#!/usr/bin/env python3

import os
import sys

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

from nwg_panel.tools import (eprint, update_image_fallback_desktop, load_json, load_shell_data)
from nwg_panel.mango_ipc import get_mango_ipc

dir_name = os.path.dirname(os.path.dirname(__file__))

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

        self.voc = None
        self.shell_data = load_shell_data()

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
            "show-tags-from-all-monitors": False,  # determines if to show all monitors->tags, or just the current monitor
            "sort-monitors-by-x": True,            # outputs may be sorted by their x coordinate or alphabetically
            "show-layout": True,                   # determines if to show per-monitor layout symbol
            "show-per-tag-window-icons": True,     # determines if to show per-tag client icons
            "icon-size": 16,                       # client icon size
            "show-per-tag-window-names": True,     # determines if to show per-tag client titles
            "name-length": 20,                     # limits client title length
            "show-empty-tags": False,              # determines if to show labels for tags with no client
            "scratchpad-label": "SCR:",            # defines scratchpad label
            "angle": 0.0                           # use 90 or 270 for vertical panels
        }
        for key in defaults:
            if key not in self.settings:
                self.settings[key] = defaults[key]

        if self.settings["angle"] != 0.0:
            self.set_orientation(Gtk.Orientation.VERTICAL)

        self.load_vocabulary()

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
                        lbl = Gtk.Label.new()
                        lbl.set_markup(f"<span size='xx-small'><b>{_i['layout_symbol']}</b></span>")
                        if self.settings["angle"] != 0.0:
                            lbl.set_angle(self.settings["angle"])
                        lbl.set_property("name", "mango-tags-layout-label")
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

                            self.pack_start(eb, False, False, 3)

                            # tag index label
                            tag_idx_lbl = Gtk.Label.new(f"{i['index']}")
                            tag_idx_lbl.set_property("name", "mango-tags-index-label")
                            if self.settings["angle"] != 0.0:
                                tag_idx_lbl.set_angle(self.settings["angle"])
                            eb.add(tag_idx_lbl)

                            for client in self.all_clients:
                                # filter out clients in scratchpad
                                if client.get("is_scratchpad") or client.get("is_namedscratchpad"):
                                    continue

                                if client["monitor"] == m_name and i["index"] in client["tags"]:
                                    # client icon and title
                                    eb_icon_title = Gtk.EventBox()
                                    eb_icon_title.set_tooltip_text(client["title"])
                                    eb_icon_title.connect("button-release-event", self.on_client_clicked, client["id"])
                                    inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                                    eb_icon_title.add(inner_box)

                                    if self.settings["show-per-tag-window-icons"] or self.settings["show-per-tag-window-names"]:
                                        self.pack_start(eb_icon_title, False, False, 3)

                                    # icon
                                    if self.settings["show-per-tag-window-icons"]:
                                        icon = Gtk.Image()
                                        icon.set_property("name", "mango-tags-app-icon")
                                        try:
                                            update_image_fallback_desktop(
                                                icon, client["appid"], self.settings["icon-size"], self.icons_path,
                                                fallback=False
                                            )
                                            inner_box.pack_start(icon, False, False, 0)
                                        except Exception as e:
                                            eprint(
                                                f"MangoTags: could not update per-ws icon for appid '{client['appid']}'", e)

                                    # title
                                    if self.settings["show-per-tag-window-names"]:
                                        max_len = self.settings["name-length"]
                                        display_title = client['title'] if len(client['title']) <= max_len else f"{client['title'][:max_len]}…"
                                        lbl = Gtk.Label.new(f"{display_title}")
                                        lbl.set_property("name", "mango-tags-client-title")
                                        if self.settings["angle"] != 0.0:
                                            lbl.set_angle(self.settings["angle"])

                                        inner_box.pack_start(lbl, False, False, 0)

                                    if not self.settings["show-per-tag-window-icons"] and not self.settings["show-per-tag-window-names"]:
                                        # mark non-empty tags w/ a dot if we don't show neither window icon nor title
                                        if not tag_idx_lbl.get_text().endswith("."):
                                            tag_idx_lbl.set_text(f"{tag_idx_lbl.get_text()}.")

            scratchpad_clients = [
                c for c in self.all_clients
                if c["monitor"] == m_name and (c.get("is_scratchpad") or c.get("is_namedscratchpad"))
            ]

            if scratchpad_clients:
                # scratchpad label
                lbl = Gtk.Label.new()
                lbl.set_markup(f"<span size='xx-small'><b>{self.settings["scratchpad-label"]}</b></span>")
                lbl.set_property("name", "mango-scratchpad-label")
                self.pack_start(lbl, False, False, 3)

                drawer_eb = Gtk.EventBox()
                drawer_eb.set_property("name", "mango-scratchpad")
                drawer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                drawer_eb.add(drawer_box)
                self.pack_start(drawer_eb, False, False, 6)

                for client in scratchpad_clients:
                    eb_icon_title = Gtk.EventBox()
                    eb_icon_title.set_tooltip_text(client["title"])
                    eb_icon_title.connect("button-release-event", self.on_client_clicked, client["id"])

                    # client icon
                    if self.settings["show-per-tag-window-icons"]:
                        icon = Gtk.Image()
                        icon.set_property("name", "mango-tags-app-icon")
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


    def load_vocabulary(self):
        # basic vocabulary (for en_US)
        self.voc = load_json(os.path.join(dir_name, "langs", "en_US.json"))
        if not self.voc:
            eprint("Failed loading vocabulary")
            sys.exit(1)

        lang = os.getenv("LANG").split(".")[0] if not self.shell_data["interface-locale"] else self.shell_data["interface-locale"]
        # translate if translation available
        if lang != "en_US":
            loc_file = os.path.join(dir_name, "langs", "{}.json".format(lang))
            if os.path.isfile(loc_file):
                # localized vocabulary
                loc = load_json(loc_file)
                if not loc:
                    eprint("Failed loading translation into '{}'".format(lang))
                else:
                    for key in loc:
                        self.voc[key] = loc[key]

    def on_client_clicked(self, widget, event, client_id):
        if event.button == 1:
            cmd = f"dispatch focusid client,{client_id}"
            get_mango_ipc(cmd)

        elif event.button == 3:  # right click context menu
            menu = Gtk.Menu()

            item_fs = Gtk.MenuItem.new_with_label(self.voc["toggle-full-screen"])
            item_fs.connect("activate", lambda w: get_mango_ipc(f"dispatch togglefullscreen client,{client_id}"))
            menu.append(item_fs)

            item_float = Gtk.MenuItem.new_with_label(self.voc["toggle-floating"])
            item_float.connect("activate", lambda w: get_mango_ipc(f"dispatch togglefloating client,{client_id}"))
            menu.append(item_float)

            item_scratch = Gtk.MenuItem.new_with_label(self.voc["to-scratchpad"])
            item_scratch.connect("activate", lambda w: get_mango_ipc(f"dispatch minimized client,{client_id}"))
            menu.append(item_scratch)

            menu.append(Gtk.SeparatorMenuItem())

            item_kill = Gtk.MenuItem.new_with_label(self.voc["close-window"])
            item_kill.connect("activate", lambda w: get_mango_ipc(f"dispatch killclient client,{client_id}"))
            menu.append(item_kill)

            menu.show_all()
            menu.popup_at_pointer(None)
