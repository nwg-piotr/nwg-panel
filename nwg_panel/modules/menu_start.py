#!/usr/bin/env python3

from gi.repository import Gtk

import os
import subprocess

from nwg_panel.tools import check_key, update_image


def desktop_dirs():
    local = os.path.join(os.getenv("XDG_DATA_HOME"), ".local/share") if os.getenv(
        "XDG_DATA_HOME") else os.path.expanduser('~/.local/share')
    paths = [local, "/usr/share", "/usr/local/share"]

    if os.getenv("XDG_DATA_DIRS"):
        for item in os.getenv("XDG_DATA_DIRS").split(":"):
            if item not in paths:
                paths.append(item)

    # Before reported as a "bug": add flatpak if not found in XDG_DATA_DIRS
    for p in [os.path.expanduser("~/.local/share/flatpak/exports/share"),
              "/var/lib/flatpak/exports/share"]:
        if p not in paths:
            paths.append(p)

    return [os.path.join(p, 'applications') for p in paths]


class MenuStart(Gtk.Button):
    def __init__(self, settings, icons_path=""):
        print(desktop_dirs())

        Gtk.Button.__init__(self)
        self.set_always_show_image(True)
        self.settings = settings

        check_key(settings, "icon", "dialog-error")
        check_key(settings, "icon-size", 16)

        image = Gtk.Image()
        update_image(image, "start-here", settings["icon-size"], icons_path)
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
