#!/usr/bin/env python3

from gi.repository import Gtk

import subprocess

from nwg_panel.tools import check_key, update_image


class CustomButton(Gtk.Button):
    def __init__(self, settings, icons_path=""):
        Gtk.Button.__init__(self)
        self.set_always_show_image(True)
        self.settings = settings

        check_key(settings, "icon", "dialog-error")
        check_key(settings, "icon-size", 16)
        image = Gtk.Image()
        update_image(image, settings["icon"], settings["icon-size"], icons_path)
        self.set_image(image)

        check_key(settings, "label", "")
        if "label" in settings and settings["label"]:
            if "label-position" in settings:
                if settings["label-position"] == "right":
                    self.set_image_position(Gtk.PositionType.LEFT)
                    self.set_label(settings["label"])
                elif settings["label-position"] == "left":
                    self.set_image_position(Gtk.PositionType.RIGHT)
                    self.set_label(settings["label"])
                elif settings["label-position"] == "top":
                    self.set_image_position(Gtk.PositionType.BOTTOM)
                    self.set_label(settings["label"])
                elif settings["label-position"] == "bottom":
                    self.set_image_position(Gtk.PositionType.TOP)
                    self.set_label(settings["label"])
                else:
                    self.set_tooltip_text(settings["label"])
            else:
                self.set_tooltip_text(settings["label"])

        if "tooltip" in settings and settings["tooltip"]:
            self.set_tooltip_text(settings["tooltip"])

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
