#!/usr/bin/env python3

from gi.repository import Gtk, Gdk

import sys
import subprocess

sys.path.append('../')

from nwg_panel.tools import check_key


class Controls(Gtk.Button):
    def __init__(self, settings):
        Gtk.Button.__init__(self)
        self.settings = settings

        check_key(settings, "icon", "nwgocc")
        image = Gtk.Image.new_from_icon_name(settings["icon"], Gtk.IconSize.MENU)
        self.set_image(image)

        self.connect("clicked", self.on_click)

        self.show()

    def on_click(self, button):
        print("CC clicked")
        menu = Gtk.Menu()
        item = Gtk.MenuItem.new_with_label("gtk-layer-shell")
        menu.append(item)
        item = Gtk.MenuItem.new_with_label("is a very fucking awesome")
        menu.append(item)
        item = Gtk.MenuItem.new_with_label("thing!")
        menu.append(item)
        menu.show_all()
        menu.popup_at_widget(self, Gdk.Gravity.CENTER, Gdk.Gravity.NORTH_WEST, None)
