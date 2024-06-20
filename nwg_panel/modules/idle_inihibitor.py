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

from nwg_panel.tools import check_key, update_image


class IdleInhibitor(Gtk.EventBox):
    def __init__(self, settings, icons_path):
        Gtk.EventBox.__init__(self)
        self.icons_path = icons_path
        self.image = Gtk.Image()

        check_key(settings, "icon-size", 16)
        check_key(settings, "active", False)

        if settings["active"]:
            update_image(self.image, "idle-inhibitor-active", settings["icon-size"], self.icons_path)
        else:
            update_image(self.image, "idle-inhibitor-inactive", settings["icon-size"], self.icons_path)

        self.add(self.image)


@dataclass
class GlobalRegistry:
    surface: WlSurface | None = None
    inhibit_manager: ZwpIdleInhibitManagerV1 | None = None


def handle_registry_global(
        wl_registry: WlRegistryProxy, id_num: int, iface_name: str, version: int
) -> None:
    global_registry: GlobalRegistry = wl_registry.user_data or GlobalRegistry()

    if iface_name == "wl_compositor":
        compositor = wl_registry.bind(id_num, WlCompositor, version)
        global_registry.surface = compositor.create_surface()  # type: ignore
    elif iface_name == "zwp_idle_inhibit_manager_v1":
        global_registry.inhibit_manager = wl_registry.bind(
            id_num, ZwpIdleInhibitManagerV1, version
        )


def main() -> None:
    done = Event()
    signal(SIGINT, lambda _, __: done.set())
    signal(SIGTERM, lambda _, __: done.set())

    global_registry = GlobalRegistry()

    display = Display()
    display.connect()

    registry = display.get_registry()  # type: ignore
    registry.user_data = global_registry
    registry.dispatcher["global"] = handle_registry_global

    def shutdown() -> None:
        display.dispatch()
        display.roundtrip()
        display.disconnect()

    display.dispatch()
    display.roundtrip()

    if global_registry.surface is None or global_registry.inhibit_manager is None:
        print("Wayland seems not to support idle_inhibit_unstable_v1 protocol.")
        shutdown()
        sys.exit(1)

    inhibitor = global_registry.inhibit_manager.create_inhibitor(  # type: ignore
        global_registry.surface
    )

    display.dispatch()
    display.roundtrip()

    print("Inhibiting idle...")
    done.wait()
    print("Shutting down...")

    inhibitor.destroy()

    shutdown()


if __name__ == "__main__":
    main()
