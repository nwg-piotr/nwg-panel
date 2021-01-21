#!/usr/bin/env python3

from gi.repository import Gtk

import sys
import subprocess

sys.path.append('../')

from nwg_panel.tools import check_key


class CustomButton(Gtk.Button):
    def __init__(self, settings):
        Gtk.Button.__init__(self)
        self.settings = settings

        check_key(settings, "icon", "dialog-error")
        image = Gtk.Image.new_from_icon_name(settings["icon"], Gtk.IconSize.MENU)
        self.set_image(image)

        check_key(settings, "command", "")
        if settings["command"]:
            self.connect("clicked", self.on_click, settings["command"])

        check_key(settings, "css-name", "")
        if settings["css-name"]:
            self.set_property("name", settings["css-name"])

        self.show()

    def on_click(self, button, cmd):
        if cmd:
            print("Executing '{}'".format(cmd))
            subprocess.Popen('exec {}'.format(cmd), shell=True)
        else:
            print("No command assigned")
