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
        self.build_box()

    def build_box(self):
        check_key(self.settings, "numbers", [1, 2, 3, 4, 5, 6, 7, 8])
        f = self.focused_ws()
        for num in self.settings["numbers"]:
            eb = Gtk.EventBox()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            eb.add(box)
            self.pack_start(eb, False, False, 0)
            lbl = Gtk.Label(str(num))
            self.ws_num2box[num] = eb
            box.pack_start(lbl, False, False, 6)
            eb.connect("enter_notify_event", self.on_enter_notify_event)
            eb.connect("leave_notify_event", self.on_leave_notify_event)
            eb.connect("button-press-event", self.on_click, num)
            
            self.pack_start(box, False, False, 0)
            if num == str(f):
                eb.set_property("name", "task-box-focused")
            else:
                eb.set_property("name", "task-box")

        self.show_all()

    def on_click(self, w, e, num):
        nwg_panel.common.i3.command("workspace number {}".format(num))

    def on_enter_notify_event(self, widget, event):
        widget.get_style_context().set_state(Gtk.StateFlags.SELECTED)

    def on_leave_notify_event(self, widget, event):
        widget.get_style_context().set_state(Gtk.StateFlags.NORMAL)
        
    def highlight_active(self):
        f = self.focused_ws()
        if f > 0:
            for num in self.settings["numbers"]:
                if num == str(f):
                    self.ws_num2box[num].set_property("name", "task-box-focused")
                else:
                    self.ws_num2box[num].set_property("name", "task-box")
    
    def refresh(self):
        thread = threading.Thread(target=self.highlight_active)
        thread.daemon = True
        thread.start()
        return True

    def focused_ws(self):
        workspaces = self.i3.get_workspaces()
        for ws in workspaces:
            if ws.focused:
                return ws.num

        return -1
