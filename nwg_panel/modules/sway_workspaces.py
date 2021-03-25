#!/usr/bin/env python3

import threading

from gi.repository import Gtk

import nwg_panel.common
from nwg_panel.tools import check_key


class SwayWorkspaces(Gtk.Box):
    def __init__(self, settings, i3):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.settings = settings
        self.i3 = i3
        self.ws_num2box = {}
        self.name_label = Gtk.Label("")
        self.build_box()

    def build_box(self):
        check_key(self.settings, "numbers", [1, 2, 3, 4, 5, 6, 7, 8])
        check_key(self.settings, "show-name", True)
        check_key(self.settings, "name-length", 40)

        ws_num, win_name = self.find_focused()

        for num in self.settings["numbers"]:
            eb = Gtk.EventBox()
            eb.connect("enter_notify_event", self.on_enter_notify_event)
            eb.connect("leave_notify_event", self.on_leave_notify_event)
            eb.connect("button-press-event", self.on_click, num)
            self.pack_start(eb, False, False, 0)

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            eb.add(box)

            lbl = Gtk.Label(str(num))
            self.ws_num2box[num] = eb

            box.pack_start(lbl, False, False, 6)

            if num == str(ws_num):
                eb.set_property("name", "task-box-focused")
            else:
                eb.set_property("name", "task-box")

        if self.settings["show-name"]:
            self.pack_start(self.name_label, False, False, 6)

        self.show_all()

    def on_click(self, w, e, num):
        nwg_panel.common.i3.command("workspace number {}".format(num))

    def on_enter_notify_event(self, widget, event):
        widget.get_style_context().set_state(Gtk.StateFlags.SELECTED)

    def on_leave_notify_event(self, widget, event):
        widget.get_style_context().set_state(Gtk.StateFlags.NORMAL)
        
    def highlight_active(self):
        ws_num, win_name = self.find_focused()
        if ws_num > 0:
            for num in self.settings["numbers"]:
                if num == str(ws_num):
                    self.ws_num2box[num].set_property("name", "task-box-focused")
                else:
                    self.ws_num2box[num].set_property("name", "task-box")

        self.name_label.set_text(win_name)
    
    def refresh(self):
        thread = threading.Thread(target=self.highlight_active)
        thread.daemon = True
        thread.start()
        return True

    def find_focused(self):
        tree = self.i3.get_tree()
        workspaces = self.i3.get_workspaces()
        ws_num = -1
        win_name = ""

        for ws in workspaces:
            if ws.focused:
                ws_num = ws.num

        if self.settings["show-name"]:
            f = self.i3.get_tree().find_focused()
            if f.type == "con" and f.name and str(f.parent.workspace().num) in self.settings["numbers"]:
                win_name = f.name[:self.settings["name-length"]]

            for item in tree.descendants():
                if item.type == "workspace":
                    for node in item.floating_nodes:
                        if str(node.workspace().num) in self.settings["numbers"] and node.focused:
                            win_name = node.name

        return ws_num, win_name
