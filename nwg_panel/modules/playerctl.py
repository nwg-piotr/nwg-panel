#!/usr/bin/env python3
import os.path

from gi.repository import GLib

import subprocess
import threading
import requests

from nwg_panel.tools import check_key, update_image, player_status, player_metadata, eprint, local_dir

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk

from urllib.parse import unquote, urlparse


class Playerctl(Gtk.EventBox):
    def __init__(self, settings, icons_path=""):
        self.settings = settings
        self.icons_path = icons_path
        Gtk.EventBox.__init__(self)
        check_key(settings, "interval", 1)
        check_key(settings, "label-css-name", "")
        check_key(settings, "button-css-name", "")
        check_key(settings, "icon-size", 16)
        check_key(settings, "buttons-position", "left")
        check_key(settings, "chars", 30)
        check_key(settings, "scroll", True)
        check_key(settings, "show-cover", True)
        check_key(settings, "cover-size", 24)
        check_key(settings, "angle", 0.0)

        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        if settings["angle"] != 0.0:
            self.box.set_orientation(Gtk.Orientation.VERTICAL)

        self.box.set_property("name", "task-box")
        self.add(self.box)
        self.image = Gtk.Image()
        update_image(self.image, "view-refresh-symbolic", self.settings["icon-size"], icons_path=self.icons_path)
        self.label = Gtk.Label.new("")
        self.icon_path = None
        self.play_pause_btn = Gtk.Button()
        check_key(settings, "button-css-name", "")
        if self.settings["button-css-name"]:
            self.play_pause_btn.set_property("name", self.settings["button-css-name"])
        self.status = ""
        self.retries = 2  # to avoid hiding the module on forward / backward btn when playing from the browser

        self.output_start_idx = 0
        self.old_metadata = ""
        self.old_cover_url = ""

        self.cover_img = Gtk.Image()
        update_image(self.cover_img, "music", settings["cover-size"], icons_path)

        if settings["label-css-name"]:
            self.label.set_property("name", settings["label-css-name"])

        self.label.set_angle(settings["angle"])

        self.build_box()

        self.refresh()

        if settings["interval"] > 0:
            Gdk.threads_add_timeout_seconds(GLib.PRIORITY_LOW, settings["interval"], self.refresh)

    def update_remote_cover(self, url):
        try:
            r = requests.get(url, allow_redirects=True)
            cover_path = os.path.join(local_dir(), "cover.jpg")
            with open(cover_path, 'wb') as f:
                f.write(r.content)
            update_image(self.cover_img, cover_path, self.settings["cover-size"], fallback=False)
            self.cover_img.show()
        except Exception as e:
            eprint("Couldn't update remote cover: {}".format(e))
            update_image(self.cover_img, "music", self.settings["cover-size"], self.icons_path)

    def update_cover_image(self, url):
        if url.startswith("file:"):
            try:
                update_image(self.cover_img, unquote(urlparse(url).path), self.settings["cover-size"], fallback=False)
                self.cover_img.show()
            except Exception as e:
                eprint("Error creating pixbuf: {}".format(e))
                update_image(self.cover_img, "music", self.settings["cover-size"], self.icons_path)

        if url.startswith("http"):
            thread = threading.Thread(target=self.update_remote_cover(url))
            thread.daemon = True
            thread.start()

        elif not url:
            self.cover_img.hide()

    def update_widget(self, status, metadata):
        text = metadata["text"]
        self.label.set_tooltip_text(text)
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
                    text = "{} - paused".format(text)

            # reset (scrolling) if track changed
            if metadata != self.old_metadata:
                self.output_start_idx = 0
                self.update_cover_image(metadata["url"])
                self.old_metadata = metadata

            if not self.settings["scroll"]:
                self.label.set_text(text)
            else:
                # scroll track metadata of 1 character once settings["interval"]
                if len(text) > self.settings["chars"]:
                    if self.output_start_idx + self.settings["chars"] <= len(text):
                        self.label.set_text(
                            text[self.output_start_idx:self.output_start_idx + self.settings["chars"]])
                        self.output_start_idx += 1
                    else:
                        self.label.set_text(text[:self.settings["chars"]])
                        self.output_start_idx = 0
                else:
                    self.label.set_text(text)
        else:
            if self.get_visible():
                if self.retries == 0:
                    self.hide()
                else:
                    self.retries -= 1

        return False

    def get_output(self):
        metadata = {"text": "", "url": ""}
        try:
            status = player_status()
            if status in ["Playing", "Paused"]:
                metadata = player_metadata()
                if not self.settings["scroll"] and len(metadata["text"]) > self.settings["chars"]:
                    metadata["text"] = metadata["text"][:self.settings["chars"] - 1]
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
        if self.settings["angle"] != 0.0:
            button_box.set_orientation(Gtk.Orientation.VERTICAL)

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
            if self.settings["show-cover"]:
                self.box.pack_start(self.cover_img, False, False, 0)
            self.box.pack_start(self.label, False, False, 10)
        else:
            if self.settings["show-cover"]:
                self.box.pack_start(self.cover_img, False, False, 2)
            self.box.pack_start(self.label, False, False, 2)
            self.box.pack_start(button_box, False, False, 10)

    def launch(self, button, cmd):
        subprocess.Popen('exec {}'.format(cmd), shell=True)
