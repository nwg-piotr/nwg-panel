#!/usr/bin/env python3

from gi.repository import Gtk

import subprocess

from nwg_panel.tools import check_key, update_image


class MenuStart(Gtk.Button):
    def __init__(self, settings, icons_path=""):
        Gtk.Button.__init__(self)
        self.set_always_show_image(True)
        self.settings = settings
        self.set_property("name", "button-start")

        check_key(settings, "icon", "dialog-error")
        check_key(settings, "icon-size", 18)

        image = Gtk.Image()
        update_image(image, "nwg-shell", settings["icon-size"], icons_path)
        self.set_image(image)

        self.connect("clicked", self.on_click)

        check_key(settings, "css-name", "")
        if settings["css-name"]:
            self.set_property("name", settings["css-name"])

        self.show()

    def on_click(self, button):
        cmd = "nwg-panel-plugin-menu"
        """settings = {
            "output": panel["output"],
            "position": panel["position"],
            "alignment": "left",
            "margin-left": 6,
            "margin-bottom": 6
        }"""
        if self.settings["output"]:
            cmd += " -o {}".format(self.settings["output"])
        
        if self.settings["position"]:
            cmd += " -p {}".format(self.settings["position"])

        if self.settings["alignment"]:
            cmd += " -a {}".format(self.settings["alignment"])

        if self.settings["margin-left"]:
            cmd += " -ml {}".format(self.settings["margin-left"])

        if self.settings["margin-bottom"]:
            cmd += " -mb {}".format(self.settings["margin-bottom"])

        if self.settings["autohide"]:
            cmd += " -d"

        print("Executing '{}'".format(cmd))
        subprocess.Popen('exec {}'.format(cmd), shell=True)
