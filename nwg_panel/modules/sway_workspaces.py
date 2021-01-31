#!/usr/bin/env python3

from gi.repository import Gtk

import nwg_panel.common
from nwg_panel.tools import check_key


class SwayWorkspaces(Gtk.Box):
    def __init__(self, settings):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.settings = settings
        self.build_box()

    def build_box(self):
        check_key(self.settings, "numbers", [1, 2, 3, 4, 5, 6, 7, 8])
        for num in self.settings["numbers"]:
            btn = Gtk.Button.new_with_label("{}".format(num))
            btn.connect("clicked", self.on_click, num)
            self.pack_start(btn, False, False, 0)

        self.show_all()

    def on_click(self, button, num):
        nwg_panel.common.i3.command("workspace number {}".format(num))
