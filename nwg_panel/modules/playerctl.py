#!/usr/bin/env python3

from gi.repository import GLib

import subprocess
import threading

from nwg_panel.tools import check_key, update_image, player_status, player_metadata

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk


class Playerctl(Gtk.EventBox):
    def __init__(self, settings, icons_path=""):
        self.settings = settings
        self.icons_path = icons_path
        Gtk.EventBox.__init__(self)
        check_key(settings, "interval", 20)
        check_key(settings, "label-css-name", "")
        check_key(settings, "button-css-name", "")
        check_key(settings, "icon-size", 16)
        check_key(settings, "buttons-position", "left")
        check_key(settings, "chars", 30)

        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.box.set_property("name", "task-box")
        self.add(self.box)
        self.image = Gtk.Image()
        update_image(self.image, "view-refresh-symbolic", self.settings["icon-size"], icons_path=self.icons_path)
        self.label = Gtk.Label("")
        self.icon_path = None
        self.play_pause_btn = Gtk.Button()
        check_key(settings, "button-css-name", "")
        if self.settings["button-css-name"]:
            self.play_pause_btn.set_property("name", self.settings["button-css-name"])
        self.status = ""
        self.retries = 2  # to avoid hiding the module on forward / backward btn when playing from the browser

        if settings["label-css-name"]:
            self.label.set_property("name", settings["label-css-name"])

        self.build_box()

        self.refresh()

        if settings["interval"] > 0:
            Gdk.threads_add_timeout(GLib.PRIORITY_LOW, settings["interval"], self.refresh)

    def update_widget(self, status, metadata):
        if status in ["Playing", "Paused"]:
            self.retries = 2
            if not self.get_visible():
                self.show()

            if not self.status == status:
                if status == "Playing":
                    update_image(self.play_pause_btn.get_image(), "media-playback-pause-symbolic",
                                 self.settings["icon-size"], icons_path=self.icons_path)
                elif status == "Paused":
                    update_image(self.play_pause_btn.get_image(), "media-playback-start-symbolic",
                                 self.settings["icon-size"], icons_path=self.icons_path)
                    metadata = "{} - paused".format(metadata)

            self.label.set_text(metadata)
        else:
            if self.get_visible():
                if self.retries == 0:
                    self.hide()
                else:
                    self.retries -= 1

        return False

    def get_output(self):
        status, metadata = "", ""
        try:
            status = player_status()
            if status in ["Playing", "Paused"]:
                metadata = player_metadata()[:self.settings["chars"]]
            GLib.idle_add(self.update_widget, status, metadata)
        except Exception as e:
            print(e)

    def refresh(self):
        thread = threading.Thread(target=self.get_output)
        thread.daemon = True
        thread.start()
        return True

    def build_box(self):
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        img = Gtk.Image()
        update_image(img, "media-skip-backward-symbolic", self.settings["icon-size"], icons_path=self.icons_path)
        btn = Gtk.Button()
        btn.set_image(img)
        if self.settings["button-css-name"]:
            btn.set_property("name", self.settings["button-css-name"])
        btn.connect("clicked", self.launch, "playerctl previous")
        button_box.pack_start(btn, False, False, 1)

        img = Gtk.Image()
        update_image(img, "media-playback-start-symbolic", self.settings["icon-size"], icons_path=self.icons_path)
        self.play_pause_btn.set_image(img)
        self.play_pause_btn.connect("clicked", self.launch, "playerctl play-pause")
        button_box.pack_start(self.play_pause_btn, False, False, 1)

        img = Gtk.Image()
        update_image(img, "media-skip-forward-symbolic", self.settings["icon-size"], icons_path=self.icons_path)
        btn = Gtk.Button()
        btn.set_image(img)
        if self.settings["button-css-name"]:
            btn.set_property("name", self.settings["button-css-name"])
        btn.connect("clicked", self.launch, "playerctl next")
        button_box.pack_start(btn, False, False, 1)

        if self.settings["buttons-position"] == "left":
            self.box.pack_start(button_box, False, False, 2)
            self.box.pack_start(self.label, False, False, 10)
        else:
            self.box.pack_start(self.label, False, False, 2)
            self.box.pack_start(button_box, False, False, 10)

    def launch(self, button, cmd):
        subprocess.Popen('exec {}'.format(cmd), shell=True)
