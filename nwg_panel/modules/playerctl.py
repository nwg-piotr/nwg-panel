#!/usr/bin/env python3
from enum import Enum
import os.path
import threading
from urllib.parse import unquote, urlparse

import gi

gi.require_version('Playerctl', '2.0')

from gi.repository import GLib, Gtk, Gdk
from gi.repository import Playerctl as Ctl
import requests

from nwg_panel.tools import check_key, eprint, local_dir, update_image


class Playerctl(Gtk.EventBox):
    PlayerOps = Enum('PlayerOps', ['PLAY_PAUSE', 'NEXT', 'PREVIOUS'])

    def __init__(self, settings, voc, icons_path=""):
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
        check_key(settings, "button-css-name", "")

        self.voc = voc

        self.old_cover_url = ""
        self.old_media_info = ""

        self.player = None
        self.player_handler_ids = []

        self.num_players = 0
        self.player_idx = 0
        self.add_events(Gdk.EventMask.SCROLL_MASK)
        self.connect('scroll-event', self.on_scroll)

        self.build_box()
        self.subscribe()

        # Hide on start if no player presents
        def hide_self(_):
            if not self.player:
                self.hide()

        self.connect("realize", hide_self)

    def subscribe(self):
        # Must associate manager with self to increase its reference count
        self.manager = Ctl.PlayerManager()
        self.manager.connect('name-appeared', self.on_name_appeared)
        self.manager.connect('player-vanished', self.on_player_vanished)

        # Manage all players from old to new, so that the newest one comes
        # first in props.players
        for name in reversed(self.manager.props.player_names):
            self.manage_player_by_name(self.manager, name)

        self.num_players = len(self.manager.props.players)
        if self.num_players > 1:
            self.num_players_lbl.set_text(f" {self.player_idx + 1}/{self.num_players} ")
            self.num_players_lbl.set_tooltip_text(
                f"Player {self.player_idx + 1}/{self.num_players}, {self.voc['scroll-to-switch']}")
        else:
            self.num_players_lbl.set_text("")

        if len(self.manager.props.players) > 0:
            self.init_player(self.manager.props.players[self.player_idx])

    @staticmethod
    def manage_player_by_name(manager, name):
        player = Ctl.Player.new_from_name(name)
        manager.manage_player(player)

    def on_name_appeared(self, manager, name):
        self.subscribe()
        self.deinit_player()
        self.manage_player_by_name(manager, name)
        self.init_player(manager.props.players[self.player_idx])

    def on_player_vanished(self, manager, player):
        self.subscribe()
        # Non-active player vanished, do nothing
        if self.player and player.props.player_name != self.player.props.player_name:
            return

        # Active player vanished, populate another one if exists
        self.deinit_player()
        if len(manager.props.players) > 0:
            self.init_player(manager.props.players[self.player_idx])

    def init_player(self, player):
        self.player = player
        self.show()

        # connect signals
        self.player_handler_ids.append(
            player.connect('metadata', self.on_metadata))
        self.player_handler_ids.append(
            player.connect('playback-status', self.on_playback_status))

        # Manually set the initial state
        # self.on_metadata(player, player.props.metadata)
        self.on_metadata(player, [])

    def deinit_player(self):
        if self.player:
            for handler_id in self.player_handler_ids:
                self.player.disconnect(handler_id)
        self.player = None
        self.player_handler_ids.clear()
        self.hide()

    def on_playback_status(self, player, status):
        artist = player.get_artist()
        title = player.get_title()
        status_text = None

        if status == Ctl.PlaybackStatus.PLAYING:
            update_image(self.play_pause_btn.get_image(), "media-playback-pause-symbolic",
                         self.settings["icon-size"], icons_path=self.icons_path)
        else:
            update_image(self.play_pause_btn.get_image(), "media-playback-start-symbolic",
                         self.settings["icon-size"], icons_path=self.icons_path)
            if status == Ctl.PlaybackStatus.PAUSED:
                status_text = "paused"
            elif status == Ctl.PlaybackStatus.STOPPED:
                status_text = "stopped"

        # Filter out empty value when building info
        info = [x for x in (artist, title, status_text) if x]
        info = " - ".join(info)
        self.set_media_info(info)

    def on_metadata(self, player, metadata):
        try:
            cover_url = metadata["mpris:artUrl"]
        except:  # used to be on KeyError, but actual error is 'mpris:artUrl' for some reason (playerctl bug?)
            cover_url = ""

        if cover_url != self.old_cover_url:
            self.old_cover_url = cover_url
            self.update_cover_image(cover_url)

        self.on_playback_status(player, player.props.playback_status)

    def update_remote_cover(self, url):
        try:
            r = requests.get(url, allow_redirects=True)
            cover_path = os.path.join(local_dir(), "cover.jpg")
            with open(cover_path, 'wb') as f:
                f.write(r.content)
            cover_path = "file://" + cover_path
        except Exception as e:
            eprint("Couldn't update remote cover: {}".format(e))
            cover_path = ""
        GLib.idle_add(self.update_cover_image, cover_path)

    def update_cover_image(self, url):
        url = urlparse(url)
        path = unquote(url.path)

        if url.scheme.startswith("http"):
            threading.Thread(target=self.update_remote_cover(url.geturl()), daemon=True).start()
            return

        if url.scheme == "file" and path:
            try:
                update_image(self.cover_img, path, self.settings["cover-size"], fallback=False)
            except Exception as e:
                eprint("Error creating pixbuf: {}".format(e))
                path = ""

        if not path:
            update_image(self.cover_img, "music", self.settings["cover-size"], self.icons_path)

    def on_scroll(self, widget, event):
        if event.direction == Gdk.ScrollDirection.UP:
            if self.player_idx < self.num_players - 1:
                self.player_idx += 1
            else:
                self.player_idx = 0
        if event.direction == Gdk.ScrollDirection.DOWN:
            if self.player_idx > 0:
                self.player_idx -= 1
            else:
                self.player_idx = self.num_players - 1
        print(f"Switched to player {self.player_idx}")
        self.subscribe()

    def build_box(self):
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        if self.settings["angle"] != 0.0:
            self.box.set_orientation(Gtk.Orientation.VERTICAL)
        self.box.set_property("name", "task-box")
        self.add(self.box)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        if self.settings["angle"] != 0.0:
            button_box.set_orientation(Gtk.Orientation.VERTICAL)

        img = Gtk.Image()
        update_image(img, "media-skip-backward-symbolic", self.settings["icon-size"], icons_path=self.icons_path)
        btn = Gtk.Button()
        btn.set_image(img)
        if self.settings["button-css-name"]:
            btn.set_property("name", self.settings["button-css-name"])
        btn.connect("clicked", self.launch, self.PlayerOps.PREVIOUS)
        button_box.pack_start(btn, False, False, 1)

        self.play_pause_btn = Gtk.Button()
        if self.settings["button-css-name"]:
            self.play_pause_btn.set_property("name", self.settings["button-css-name"])
        img = Gtk.Image()
        update_image(img, "media-playback-start-symbolic", self.settings["icon-size"], icons_path=self.icons_path)
        self.play_pause_btn.set_image(img)
        self.play_pause_btn.connect("clicked", self.launch, self.PlayerOps.PLAY_PAUSE)
        button_box.pack_start(self.play_pause_btn, False, False, 1)

        img = Gtk.Image()
        update_image(img, "media-skip-forward-symbolic", self.settings["icon-size"], icons_path=self.icons_path)
        btn = Gtk.Button()
        btn.set_image(img)
        if self.settings["button-css-name"]:
            btn.set_property("name", self.settings["button-css-name"])
        btn.connect("clicked", self.launch, self.PlayerOps.NEXT)
        button_box.pack_start(btn, False, False, 1)

        self.num_players_lbl = Gtk.Label.new("")
        if self.settings["label-css-name"]:
            self.num_players_lbl.set_property("name", self.settings["label-css-name"])
        self.num_players_lbl.set_angle(self.settings["angle"])

        self.label = AutoScrollLabel(self.settings["scroll"],
                                     self.settings["chars"],
                                     self.settings["interval"])
        if self.settings["label-css-name"]:
            self.label.set_property("name", self.settings["label-css-name"])
        self.label.set_angle(self.settings["angle"])

        self.cover_img = Gtk.Image()
        update_image(self.cover_img, "music", self.settings["cover-size"], self.icons_path)

        if self.settings["buttons-position"] == "left":
            self.box.pack_start(button_box, False, False, 2)
            if self.settings["show-cover"]:
                self.box.pack_start(self.cover_img, False, False, 0)
            self.box.pack_start(self.num_players_lbl, False, False, 0)
            self.box.pack_start(self.label, False, False, 5)
        else:
            if self.settings["show-cover"]:
                self.box.pack_start(self.cover_img, False, False, 2)
            self.box.pack_start(self.num_players_lbl, False, False, 0)
            self.box.pack_start(self.label, False, False, 2)
            self.box.pack_start(button_box, False, False, 10)

    def launch(self, button, op):
        if not self.player:
            return

        props = self.player.props

        if op == self.PlayerOps.PLAY_PAUSE:
            status = props.playback_status
            if status == Ctl.PlaybackStatus.PLAYING:
                if not props.can_pause:
                    return
            else:
                if not props.can_play:
                    return
            self.player.play_pause()

        elif op == self.PlayerOps.PREVIOUS:
            if props.can_go_previous:
                self.player.previous()
        elif op == self.PlayerOps.NEXT:
            if props.can_go_next:
                self.player.next()

    def set_media_info(self, text):
        if self.old_media_info != text:
            self.old_media_info = text
            self.label.set_tooltip_text(text)
            self.label.set_text(text)


class AutoScrollLabel(Gtk.Label):
    def __init__(self, scroll, chars, interval):
        super().__init__(self)
        self.chars = chars
        self.interval = interval if scroll else 0

        self.output_start_idx = 0
        self.text = ""
        self.src = 0

    def set_text(self, text):
        self.text = text
        self.output_start_idx = 0
        super().set_text(text[:self.chars])

        if self.interval == 0 or len(text) <= self.chars:
            # Disable scroll
            if self.src > 0:
                GLib.Source.remove(self.src)
                self.src = 0
        else:
            # Enable scroll
            if self.src == 0:
                self.src = GLib.timeout_add_seconds(self.interval,
                                                    self.scroll_text,
                                                    priority=GLib.PRIORITY_LOW)

    def scroll_text(self):
        self.output_start_idx += 1
        if self.output_start_idx + self.chars > len(self.text):
            self.output_start_idx = 0
        super().set_text(
            self.text[self.output_start_idx:self.output_start_idx + self.chars])
        return True
