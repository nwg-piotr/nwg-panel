#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

from nwg_panel.tools import eprint, update_image_fallback_desktop, niri_outputs, niri_workspaces, niri_focused_window, niri_ipc

import json


def on_enter_notify_event(widget, event):
    widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
    widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)


def on_leave_notify_event(widget, event):
    widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
    widget.unset_state_flags(Gtk.StateFlags.SELECTED)


def on_click(event_box, event_button, id):
    # focus required workspace
    command = {"Action": {"FocusWorkspace": {"reference": {"Id": id}}}}
    niri_ipc(json.dumps(command), is_json=True)


class NiriWorkspaces(Gtk.Box):
    def __init__(self, settings, panel_output, icons_path):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        self.set_property("name", "niri-workspaces")

        # passed values
        self.settings = settings
        self.icons_path = icons_path
        self.output_name = panel_output

        # obtained in refresh()
        self.outputs_to_show = None # list of names of outputs to show workspaces for, ordered by x coordinate or alphabetically
        self.workspaces = None      # list of dicts with workspaces data, internally sorted by workspace index
        self.focused_window = None  # dictionary with focused window data

        # default settings
        defaults = {
            "show-workspaces-from-all-outputs": True,
            "sort-outputs-by-x": True,
            "show-icon": True,
            "icon-size": 16,
            "show-name": True,
            "name-length": 40,
            "angle": 0.0
        }
        for key in defaults:
            if key not in self.settings:
                self.settings[key] = defaults[key]

        if self.settings["angle"] != 0.0:
            self.set_orientation(Gtk.Orientation.VERTICAL)

        self.refresh()

    def refresh(self):
        # get output names
        outputs = niri_outputs()
        if self.settings["sort-outputs-by-x"]:
            # sort output names by output x coordinate
            output_names = sorted(
                outputs,
                key=lambda k: (outputs[k].get("logical") or {}).get("x", 0)
            )
        else:
            # sort output names alphabetically
            output_names = sorted(outputs.keys())

        # sort data and save for further use
        self.outputs_to_show = output_names if self.settings["show-workspaces-from-all-outputs"] else [self.output_name]
        self.workspaces = sorted(niri_workspaces(), key=lambda item: item["idx"])
        self.focused_window = niri_focused_window()

        self.build_box()

    def build_box(self):
        # clear old widgets
        for child in self.get_children():
            self.remove(child)

        for o in self.outputs_to_show:
            # output name label (only if we show workspaces from all outputs)
            if self.settings["show-workspaces-from-all-outputs"]:
                lbl = Gtk.Label.new(f"{o}:")
                if self.settings["angle"] != 0.0:
                    lbl.set_angle(self.settings["angle"])
                lbl.set_property("name", "niri-output-name")
                self.pack_start(lbl, False, False, 6)

            for item in self.workspaces:
                if item["output"] == o:
                    # build event box with workspace ixd (or name if given) inside, for each workspace
                    eb = Gtk.EventBox()
                    eb.connect("enter_notify_event", on_enter_notify_event)
                    eb.connect("leave_notify_event", on_leave_notify_event)
                    eb.connect("button-release-event", on_click, item["id"])

                    if item['is_focused']:
                        eb.set_property("name", "task-box-focused")
                    else:
                        eb.set_property("name", "")
                    self.pack_start(eb, False, False, 3)

                    ws_name = item["name"] if item["name"] is not None else str(item["idx"])
                    if item["is_active"]:
                        ws_name = f"{ws_name}."

                    lbl = Gtk.Label.new(f"{ws_name}")
                    lbl.set_property("name", "niri-ws-name")
                    if self.settings["angle"] != 0.0:
                        lbl.set_angle(self.settings["angle"])
                    eb.add(lbl)

        # Safety check if no window is currently focused
        focused = self.focused_window or {}
        app_id = focused.get("app_id", "")
        title = focused.get("title", "")

        if self.settings["show-icon"] and app_id:
            icon = Gtk.Image()
            icon.set_property("name", "niri-workspaces-icon")

            try:
                update_image_fallback_desktop(icon, app_id, self.settings["icon-size"], self.icons_path, fallback=False)
                self.pack_start(icon, False, False, 6)
            except:
                eprint(f"NiriWorkspaces: could not update icon for app_id '{app_id}'")

        if self.settings["show-name"] and title:
            max_len = self.settings["name-length"]
            display_title = title if len(title) <= max_len else f"{title[:max_len]}…"
            lbl = Gtk.Label.new(display_title)
            lbl.set_property("name", "niri-window-title")
            if self.settings["angle"] != 0.0:
                lbl.set_angle(self.settings["angle"])
            self.pack_start(lbl, False, False, 6)

        self.show_all()
