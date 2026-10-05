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


# remote album covers larger than this are ignored
COVER_MAX_BYTES = 5 * 1024 * 1024


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
        # One PlayerManager for the whole life of the module. It used to be recreated here, and
        # subscribe() was called from the manager's own handlers (name-appeared, player-vanished)
        # and on every scroll: the old manager lost its last reference while libplayerctl was
        # still emitting its signal -> use-after-free, panel spinning at 100% CPU (#233).
        self.manager = Ctl.PlayerManager()
        self.manager.connect('name-appeared', self.on_name_appeared)
        self.manager.connect('player-vanished', self.on_player_vanished)

        # Manage all players from old to new, so that the newest one comes
        # first in props.players
        for name in reversed(self.manager.props.player_names):
            self.manage_player_by_name(self.manager, name)

        self.select_player(0)

    def select_player(self, idx):
        """Show the player at idx (clamped), or hide when there is none."""
        players = self.manager.props.players
        self.num_players = len(players)
        if self.num_players > 1:
            self.player_idx = idx % self.num_players
            self.num_players_lbl.set_text(f" {self.player_idx + 1}/{self.num_players} ")
            self.num_players_lbl.set_tooltip_text(
                f"{self.voc['media-player']} {self.player_idx + 1}/{self.num_players}, {self.voc['scroll-to-switch']}")
        else:
            self.player_idx = 0
            self.num_players_lbl.set_text("")

        self.deinit_player(hide_widget=self.num_players == 0)
        if self.num_players > 0:
            self.init_player(players[self.player_idx])

    @staticmethod
    def manage_player_by_name(manager, name):
        player = Ctl.Player.new_from_name(name)
        manager.manage_player(player)

    def on_name_appeared(self, manager, name):
        self.manage_player_by_name(manager, name)
        self.select_player(0)  # the newest player comes first

    def on_player_vanished(self, manager, player):
        # keep the current player if it is still there (its index may have changed), else the first one
        names = [p.props.player_name for p in manager.props.players]
        current = self.player.props.player_name if self.player else None
        self.select_player(names.index(current) if current in names else 0)

    def init_player(self, player):
        self.player = player
        self.show()

        # connect signals
        self.player_handler_ids.append(
            player.connect('metadata', self.on_metadata))
        self.player_handler_ids.append(
            player.connect('playback-status', self.on_playback_status))

        # We retrieve metadata with protection against None.
        metadata = player.props.metadata
        if metadata is None:
            metadata = {}

        self.on_metadata(player, metadata)

    def deinit_player(self, hide_widget=True):
        if self.player:
            for handler_id in self.player_handler_ids:
                self.player.disconnect(handler_id)
        self.player = None
        self.player_handler_ids.clear()

        # We don't hide the widget during scrolling to prevent losing focus
        if hide_widget:
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

    def update_remote_cover(self, url, cover_url):
        # The URL comes from the player (e.g. a web page's MediaSession artwork through the
        # browser): bounded download, image content only.
        cover_path = ""
        try:
            with requests.get(url, allow_redirects=True, stream=True, timeout=(5, 15)) as r:
                r.raise_for_status()
                if not r.headers.get("Content-Type", "").startswith("image/"):
                    raise ValueError("not an image: {}".format(r.headers.get("Content-Type")))
                data = bytearray()
                for chunk in r.iter_content(65536):
                    data += chunk
                    if len(data) > COVER_MAX_BYTES:
                        raise ValueError("cover larger than {} bytes".format(COVER_MAX_BYTES))
            path = os.path.join(local_dir(), "cover.jpg")
            with open(path, 'wb') as f:
                f.write(data)
            cover_path = "file://" + path
        except Exception as e:
            eprint("Couldn't update remote cover: {}".format(e))
        if cover_url != self.old_cover_url:
            return  # the track changed while this cover was downloading: a newer download owns the image
        GLib.idle_add(self.update_cover_image, cover_path)

    def update_cover_image(self, cover_url):
        url = urlparse(cover_url)
        path = unquote(url.path)

        if url.scheme in ("http", "https"):
            if self.settings["show-cover"]:
                # in a thread: the function used to be *called* here, i.e. the download ran on the
                # GTK main loop and froze the whole panel until the server answered
                threading.Thread(target=self.update_remote_cover, args=(url.geturl(), cover_url), daemon=True).start()
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
        if self.num_players <= 1:
            return

        direction = event.direction

        # Wayland smooth scrolling support
        if direction == Gdk.ScrollDirection.SMOOTH:
            has_delta, dx, dy = event.get_scroll_deltas()
            if has_delta:
                if dy < 0:
                    direction = Gdk.ScrollDirection.UP
                elif dy > 0:
                    direction = Gdk.ScrollDirection.DOWN

        if direction == Gdk.ScrollDirection.UP:
            if self.player_idx < self.num_players - 1:
                self.player_idx += 1
            else:
                self.player_idx = 0
        elif direction == Gdk.ScrollDirection.DOWN:
            if self.player_idx > 0:
                self.player_idx -= 1
            else:
                self.player_idx = self.num_players - 1
        else:
            return

        print(f"Switched to player {self.player_idx}")

        # Memory leak fix: Just switch the active player, don't restart PlayerManager.
        # select_player() also keeps the widget shown and clamps the index if a player just vanished.
        self.select_player(self.player_idx)

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
        super().__init__()
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
