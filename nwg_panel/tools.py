#!/usr/bin/env python3

import os
import json

import gi

gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, GdkPixbuf

import common


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


def get_icon(app_name):
    for d in common.app_dirs:
        path = os.path.join(d, "{}.desktop".format(app_name))
        content = None
        if os.path.isfile(path):
            content = load_text_file(path)
        elif os.path.isfile(path.lower()):
            content = load_text_file(path.lower())
        if content:
            for line in content.splitlines():
                if line.startswith("Icon="):
                    return line.split("=")[1]
    

def get_config_dir():
    # Determine config dir path, create if not found, then create sub-dirs
    xdg_config_home = os.getenv('XDG_CONFIG_HOME')
    config_home = xdg_config_home if xdg_config_home else os.path.join(os.getenv("HOME"), ".config")
    config_dir = os.path.join(config_home, "nwg-panel")
    if not os.path.isdir(config_dir):
        print("Creating '{}'".format(config_dir))
        os.mkdir(config_dir)

    # Icon folders to store user-defined icon replacements
    icon_folder = os.path.join(config_dir, "icons_light")
    if not os.path.isdir(icon_folder):
        print("Creating '{}'".format(icon_folder))
        os.mkdir(icon_folder)

    icon_folder = os.path.join(config_dir, "icons_dark")
    if not os.path.isdir(os.path.join(icon_folder)):
        print("Creating '{}'".format(icon_folder))
        os.mkdir(icon_folder)

    return config_dir


def load_text_file(path):
    try:
        with open(path, 'r') as file:
            data = file.read()
            return data
    except Exception as e:
        print(e)
        return None


def load_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(e)
        return {}


def save_json(src_dict, path):
    with open(path, 'w') as f:
        json.dump(src_dict, f, indent=2)


def list_outputs():
    outputs = {}
    for item in common.i3.get_tree():
        if item.type == "output" and not item.name.startswith("__"):
            outputs[item.name] = {"x": item.rect.x,
                                  "y": item.rect.y,
                                  "width": item.rect.width,
                                  "height": item.rect.height}
    return outputs


def check_key(dictionary, key, default_value):
    # adds a key w/ default value if missing from the dictionary
    if key not in dictionary:
        dictionary[key] = default_value
        print('Key missing, using default: "{}": {}'.format(key, default_value))


def create_pixbuf(icon, size):
    # full path given
    if icon.startswith('/'):
        if common.icons_path:
            icon = os.path.join(common.icons_path, icon)
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon, size, size)
        except:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(os.path.join(common.dirname, 'icons_light/icon-missing.svg'),
                                                            size, size)
    # just name given
    else:
        # In case someone wrote 'name.svg' instead of just 'name' in the "icons" dictionary (config_dir/config.json)
        if icon.endswith(".svg"):
            icon = "".join(icon.split(".")[:-1])
        if common.icons_path:
            icon_svg = os.path.join(common.icons_path, (icon + ".svg"))
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_svg, size, size)
            except:
                try:
                    # if a custom icon of such name does not exist, let's try using a GTK icon
                    pixbuf = common.icon_theme.load_icon(icon, size, Gtk.IconLookupFlags.FORCE_SIZE)
                except:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                        os.path.join(common.dirname, 'icons_light/icon-missing.svg'), size, size)
        else:
            try:
                pixbuf = common.icon_theme.load_icon(icon, size, Gtk.IconLookupFlags.FORCE_SIZE)
            except:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size('icons_light/icon-missing.svg', size, size)

    return pixbuf
