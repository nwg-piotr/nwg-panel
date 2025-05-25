#!/usr/bin/env python3

import os
import subprocess

import gi

from nwg_panel.tools import check_key, update_image, load_text_file, cmd_through_compositor, get_cache_dir, eprint

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gio


def get_app_dirs():
    desktop_dirs = []

    home = os.getenv("HOME")
    xdg_data_home = os.getenv("XDG_DATA_HOME")
    xdg_data_dirs = os.getenv("XDG_DATA_DIRS") if os.getenv("XDG_DATA_DIRS") else "/usr/local/share/:/usr/share/"

    if xdg_data_home:
        desktop_dirs.append(os.path.join(xdg_data_home, "applications"))
    else:
        if home:
            desktop_dirs.append(os.path.join(home, ".local/share/applications"))

    for d in xdg_data_dirs.split(":"):
        desktop_dirs.append(os.path.join(d, "applications"))

    # Add flatpak dirs if not found in XDG_DATA_DIRS
    flatpak_dirs = [os.path.join(home, ".local/share/flatpak/exports/share/applications"),
                    "/var/lib/flatpak/exports/share/applications"]
    for d in flatpak_dirs:
        if d not in desktop_dirs:
            desktop_dirs.append(d)

    return desktop_dirs


def parse_desktop_file(file_path, lang):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except UnicodeDecodeError:
        eprint(f"Warning: Invalid .desktop file '{file_path}'")
        return None
    except OSError as e:
        eprint(f"Warning: Unable to read .desktop file '{file_path}': {e}")
        return None

    icon, _exec, name = "", "", ""
    for line in lines:
        if line.startswith("[") and line != "[Desktop Entry]":
            break
        if line.upper().startswith("ICON"):
            icon = line.split("=", 1)[1].strip()
        elif line.upper().startswith("EXEC"):
            _exec = line.split("=", 1)[1].strip()
        elif line.upper().startswith("NAME") and not name:
            name = line.split("=", 1)[1].strip()
        elif line.upper().startswith(f"NAME[{lang.upper()}]"):
            name = line.split("=", 1)[1].strip()

    if "%" in _exec:
        _exec = _exec.split("%")[0].strip()

    return icon, _exec, name


def launch(widget, cmd):
    cmd = cmd_through_compositor(cmd)
    print(f"Executing: {cmd}")
    subprocess.Popen('{}'.format(cmd), shell=True)


class Pinned(Gtk.EventBox):
    def __init__(self, settings, icons_path):
        Gtk.EventBox.__init__(self)
        self.file_monitor = None
        self.icons_path = icons_path

        check_key(settings, "limit", 0)
        check_key(settings, "icon-size", 16)
        check_key(settings, "root-css-name", "root-pinned")
        check_key(settings, "css-name", "pinned-button")
        check_key(settings, "angle", 0.0)
        self.settings = settings

        self.set_property("name", settings["root-css-name"])

        lang = os.environ.get('LANG', 'en_US.UTF-8')  # fallback to default if not set
        self.lang = lang.split('.')[0].split('_')[0]

        self.desktop_dirs = get_app_dirs()

        self.desktop_ids = []
        self.cache_file_path = os.path.join(get_cache_dir(), "nwg-pin-cache")
        if os.path.exists(self.cache_file_path):
            cache_content = load_text_file(self.cache_file_path)
            if cache_content:
                self.desktop_ids = cache_content.splitlines()
                if self.desktop_ids:
                    self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
                    self.add(self.box)
                    if settings["angle"] != 0.0:
                        self.box.set_orientation(Gtk.Orientation.VERTICAL)

                    self.build_box()
            else:
                eprint(f"Nothing found in cache: '{self.cache_file_path}'")
        else:
            eprint(f"{self.cache_file_path} file not found")

        self.setup_file_monitor()

    def build_box(self):
        for widget in self.box.get_children():
            widget.destroy()

        counter = 0
        for desktop_id in self.desktop_ids:
            for desktop_dir in self.desktop_dirs:
                desktop_file = os.path.join(desktop_dir, desktop_id)

                if os.path.exists(desktop_file):
                    icon_name, exec, name = parse_desktop_file(desktop_file, lang=self.lang)
                    if icon_name and exec:
                        image = Gtk.Image()
                        update_image(image, icon_name, self.settings["icon-size"], self.icons_path)

                        btn = Gtk.Button()
                        btn.set_image(image)
                        btn.set_property("name", self.settings["css-name"])
                        btn.set_tooltip_text(name)

                        btn.connect("clicked", launch, exec)
                        self.box.pack_start(btn, False, False, 0)
                    counter += 1
                    break

                if 0 < self.settings["limit"] <= counter:
                    break

        self.show_all()

    def setup_file_monitor(self):
        file = Gio.File.new_for_path(self.cache_file_path)
        self.file_monitor = file.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.file_monitor.connect("changed", self.on_file_changed)

    def on_file_changed(self, monitor, file, other_file, event_type):
        if event_type in [Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.CREATED]:
            print(f"{self.cache_file_path} changed, rebuilding box...")
            cache_content = load_text_file(self.cache_file_path)
            if cache_content:
                self.desktop_ids = cache_content.splitlines()
            else:
                self.desktop_ids = []
            self.build_box()
