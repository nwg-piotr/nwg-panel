#!/usr/bin/env python3

# This code is based on the wayland-idle-inhibitor by Stefan Wagner
# https://github.com/stwa/wayland-idle-inhibitor
# released under the terms of the Do What The F*ck You Want To Public License

import sys
from dataclasses import dataclass
from signal import SIGINT, SIGTERM, signal
from threading import Event

from pywayland.client.display import Display
from pywayland.protocol.idle_inhibit_unstable_v1.zwp_idle_inhibit_manager_v1 import (
    ZwpIdleInhibitManagerV1,
)
from pywayland.protocol.wayland.wl_compositor import WlCompositor
from pywayland.protocol.wayland.wl_registry import WlRegistryProxy
from pywayland.protocol.wayland.wl_surface import WlSurface

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk

from nwg_panel.tools import check_key, update_image, eprint


@dataclass
class GlobalRegistry:
    surface: WlSurface | None = None
    inhibit_manager: ZwpIdleInhibitManagerV1 | None = None


def handle_registry_global(wl_registry: WlRegistryProxy, id_num: int, iface_name: str, version: int) -> None:
    global_registry: GlobalRegistry = wl_registry.user_data or GlobalRegistry()

    if iface_name == "wl_compositor":
        compositor = wl_registry.bind(id_num, WlCompositor, version)
        global_registry.surface = compositor.create_surface()  # type: ignore
    elif iface_name == "zwp_idle_inhibit_manager_v1":
        global_registry.inhibit_manager = wl_registry.bind(id_num, ZwpIdleInhibitManagerV1, version)


def on_enter_notify_event(widget, event):
    widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
    widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)


def on_leave_notify_event(widget, event):
    widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
    widget.unset_state_flags(Gtk.StateFlags.SELECTED)


class IdleInhibitor(Gtk.EventBox):
    def __init__(self, settings, icons_path):
        Gtk.EventBox.__init__(self)
        self.settings = settings
        self.icons_path = icons_path
        self.image = Gtk.Image()

        self.inhibitor = None
        self.global_registry = GlobalRegistry()

        self.display = None

        check_key(self.settings, "icon-size", 16)
        check_key(self.settings, "active", False)

        if self.settings["active"]:
            self.startup()
        else:
            update_image(self.image, "idle-inhibitor-inactive", self.settings["icon-size"], self.icons_path)

        box = Gtk.Box.new(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(box)
        box.pack_start(self.image, False, False, 6)

        self.connect('button-release-event', self.on_button_release)
        self.connect('enter-notify-event', on_enter_notify_event)
        self.connect('leave-notify-event', on_leave_notify_event)

    def on_button_release(self, widget, event):
        if not self.settings["active"]:
            self.settings["active"] = True
            self.startup()
        else:
            self.settings["active"] = False
            self.shutdown()

    def startup(self) -> None:
        self.display = Display()
        self.display.connect()

        registry = self.display.get_registry()  # type: ignore
        registry.user_data = self.global_registry
        registry.dispatcher["global"] = handle_registry_global

        self.display.dispatch()
        self.display.roundtrip()

        if self.global_registry.surface is None or self.global_registry.inhibit_manager is None:
            eprint("Wayland seems not to support idle_inhibit_unstable_v1 protocol.")
            self.shutdown()
            sys.exit(1)

        self.inhibitor = self.global_registry.inhibit_manager.create_inhibitor(
            self.global_registry.surface)  # type: ignore

        self.display.dispatch()
        self.display.roundtrip()

        update_image(self.image, "idle-inhibitor-active", self.settings["icon-size"], self.icons_path)
        eprint("Inhibiting idle")

    def shutdown(self) -> None:
        eprint("Shutting down idle inhibitor")
        self.inhibitor.destroy()
        self.display.dispatch()
        self.display.roundtrip()
        self.display.disconnect()
        update_image(self.image, "idle-inhibitor-inactive", self.settings["icon-size"], self.icons_path)
