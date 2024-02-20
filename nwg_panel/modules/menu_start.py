#!/usr/bin/env python3
import os

from gi.repository import Gtk

import subprocess

from nwg_panel.tools import check_key, update_image, cmd_through_compositor


class MenuStart(Gtk.Button):
    def __init__(self, panel, icons_path=""):
        Gtk.Button.__init__(self)
        self.set_always_show_image(True)
        self.panel = panel
        check_key(panel, "menu-start-settings", {})
        self.settings = panel["menu-start-settings"]
        self.set_property("name", "button-start")

        check_key(self.settings, "icon-size-button", 16)
        check_key(self.settings, "run-through-compositor", True)

        image = Gtk.Image()
        update_image(image, "nwg-shell", self.settings["icon-size-button"], icons_path)
        self.set_image(image)

        self.connect("clicked", self.on_click)

        self.show()

    def on_click(self, button):
        cmd = "nwg-menu"

        if self.settings["cmd-lock"] != "swaylock -f -c 000000":
            cmd += " -cmd-lock '{}'".format(self.settings["cmd-lock"])
        if self.settings["cmd-logout"] != "swaymsg exit":
            cmd += " -cmd-logout '{}'".format(self.settings["cmd-logout"])
        if self.settings["cmd-restart"] != "systemctl reboot":
            cmd += " -cmd-restart '{}'".format(self.settings["cmd-restart"])
        if self.settings["cmd-shutdown"] != "systemctl -i poweroff":
            cmd += " -cmd-shutdown '{}'".format(self.settings["cmd-shutdown"])
        if self.settings["autohide"]:
            cmd += " -d"
        if self.settings["file-manager"] != "thunar":
            cmd += " -fm {}".format(self.settings["file-manager"])
        if self.panel["menu-start"] == "right":
            cmd += " -ha {}".format(self.panel["menu-start"])
        if self.settings["icon-size-large"] != 32:
            cmd += " -isl {}".format(self.settings["icon-size-large"])
        if self.settings["icon-size-small"] != 16:
            cmd += " -iss {}".format(self.settings["icon-size-small"])
        if self.settings["margin-bottom"] > 0:
            cmd += " -mb {}".format(self.settings["margin-bottom"])
        if self.settings["margin-left"] > 0:
            cmd += " -ml {}".format(self.settings["margin-left"])
        if self.settings["margin-right"] > 0:
            cmd += " -mr {}".format(self.settings["margin-right"])
        if self.settings["margin-top"] > 0:
            cmd += " -mt {}".format(self.settings["margin-top"])
        if self.panel["output"]:
            cmd += " -o {}".format(self.panel["output"])
        if self.settings["padding"] != 2:
            cmd += " -padding {}".format(self.settings["padding"])
        if self.settings["terminal"] != "foot":
            cmd += " -term {}".format(self.settings["terminal"])
        if self.panel["position"] != "bottom":
            cmd += " -va {}".format(self.panel["position"])

        if self.settings["run-through-compositor"]:
            if os.getenv("SWAYSOCK"):
                cmd += " -wm sway"
            elif os.getenv("HYPRLAND_INSTANCE_SIGNATURE"):
                cmd += " -wm hyprland"

        cmd = cmd_through_compositor(cmd)

        print(f"Executing: {cmd}")
        subprocess.Popen('{}'.format(cmd), shell=True)
