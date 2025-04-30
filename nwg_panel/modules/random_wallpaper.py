#!/usr/bin/env python3

from gi.repository import Gtk, Gdk, GLib, GtkLayerShell

import os
import subprocess
import random
import requests
import threading

from shutil import copyfile
from nwg_panel.tools import update_image, local_dir, cmd_through_compositor, create_background_task, eprint, save_json, \
    load_json


def on_enter_notify_event(widget, event):
    widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
    widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)


def on_leave_notify_event(widget, event):
    widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
    widget.unset_state_flags(Gtk.StateFlags.SELECTED)


class RandomWallpaper(Gtk.Button):
    def __init__(self, settings, voc, icons_path=""):
        self.image_info = {}
        defaults = {
            "source": "wallhaven.cc",
            "tags": ["nature"],
            "ratios": "16x9,16x10",
            "atleast": "1920x1080",
            "apikey": '',
            "save-path": os.getenv("HOME"),
            "local-path": "",
            "icon-size": 16,
            "interval": 0,
            "refresh-on-startup": True
        }
        for key in defaults:
            if key not in settings:
                settings[key] = defaults[key]
        self.settings = settings
        self.icons_path = icons_path
        self.wallpaper_path = os.path.join(local_dir(), "wallpaper.jpg")
        self.wallpaper_info_path = os.path.join(local_dir(), "wallpaper.json")

        self.voc = voc
        self.src_tag = 0

        Gtk.Button.__init__(self)
        self.set_always_show_image(True)
        self.settings = settings
        self.set_property("name", "random-wallpaper-button")

        image = Gtk.Image()
        update_image(image, "wallpaper", settings["icon-size"], icons_path)
        self.set_image(image)

        self.set_tooltip_text(voc["random-wallpaper"])
        self.connect('clicked', self.display_menu)

        self.connect('enter-notify-event', on_enter_notify_event)
        self.connect('leave-notify-event', on_leave_notify_event)

        self.show()

        if self.settings["refresh-on-startup"]:
            self.apply_wallpaper(None)

        if self.settings["interval"] > 0:
            self.src_tag = GLib.timeout_add_seconds(self.settings["interval"] * 60, self.apply_wallpaper, None)
            image = Gtk.Image()
            update_image(image, "wallpaper-refresh", settings["icon-size"], icons_path)
            self.set_image(image)

    def load_wallhaven_image(self):
        api_key = self.settings['apikey'] if self.settings["apikey"] else None
        api_key_status = "set" if self.settings['apikey'] else "unset"
        tags = " ".join(self.settings['tags']) if self.settings['tags'] else ""
        ratios = self.settings['ratios'] if self.settings['ratios'] else "16x9,16x10"
        atleast = self.settings["atleast"] if self.settings["atleast"] else "1920x1080"
        print(
            f"Fetching random image from wallhaven.cc, tags: '{tags}', ratios: '{ratios}', atleast: '{atleast}', API key: {api_key_status}")
        # Wallhaven API endpoint
        url = "https://wallhaven.cc/api/v1/search"

        # Parameters for the API request
        params = {
            "q": tags,
            "ratios": ratios,
            "atleast": atleast,
            "sorting": "random"
        }
        if api_key:
            params["apikey"] = api_key

        # Make the API request
        response = requests.get(url, params=params)

        # Get the image URL from the response
        if response.status_code == 200:
            image_data = response.json()
            try:
                image_url = image_data["data"][0]["path"]
            except (IndexError, KeyError):
                msg = self.voc["no-wallpaper-found"]
                tags = ",".join(self.settings["tags"])
                subprocess.Popen(f"notify-send '{msg}' {tags} -i preferences-desktop-wallpaper -t 6000",
                                 shell=True)

            self.image_info = image_data["data"][0]

            # Download the image
            image_response = requests.get(image_url)

            if image_response.status_code == 200:
                # Save the image locally
                with open(self.wallpaper_path, "wb") as file:
                    file.write(image_response.content)
                print(f"Wallhaven image saved as {self.wallpaper_path}")
                save_json(self.image_info, self.wallpaper_info_path)
                print(f"Wallhaven image info saved as {self.wallpaper_info_path}")
            else:
                eprint("Failed to download Wallhaven image")
        else:
            eprint("Failed to fetch Wallhaven image")

    def load_and_apply_local_image(self):
        if not os.path.isdir(self.settings["local-path"]):
            eprint("Local wallpaper path does not exist")
            return
        paths = os.listdir(self.settings["local-path"])
        if len(paths) == 0:
            eprint(f"No files found in {self.settings['local-path']}")
            return
        idx = random.randint(0, len(paths) - 1)
        image_path = os.path.join(self.settings["local-path"], paths[idx])
        ext = image_path.split(".")[-1]
        if ext.upper() in ["PNG", "JPG", "JPEG", "TIF", "TIFF", "SVG", 'WEBP', 'HEIC', 'AVIF']:
            print(f"Setting '{image_path}' as wallpaper")
            cmd = "pkill swaybg"
            subprocess.Popen('{}'.format(cmd), shell=True)
            print(f"Executing: {cmd}")
            subprocess.Popen('{}'.format(cmd), shell=True)

            cmd = f"swaybg -i '{image_path}' -m fill"

            cmd = cmd_through_compositor(cmd)
            print(f"Executing: {cmd}")
            subprocess.Popen(f"{cmd}", shell=True, preexec_fn=os.setpgrp)
        else:
            eprint(f"'{image_path}' is not a valid image file")

    def load_apply_wallhaven_image(self):
        self.load_wallhaven_image()

        cmd = "pkill swaybg"
        print(f"Executing: {cmd}")
        subprocess.Popen('{}'.format(cmd), shell=True)

        cmd = "swaybg -i {} -m fill".format(self.wallpaper_path)

        if os.path.isfile(self.wallpaper_path):
            cmd = cmd_through_compositor(cmd)
            print(f"Executing: {cmd}")
            subprocess.Popen('{}'.format(cmd), shell=True)
        else:
            eprint(f"'{self.wallpaper_path}' image not found")

    def apply_wallpaper(self, widget):
        if self.settings["source"] == "local":
            if os.path.isdir(self.settings["local-path"]) and len(os.listdir(self.settings["local-path"])) > 0:
                self.load_and_apply_local_image()
            else:
                eprint(f"Local wallpaper path {self.settings['local-path']} not found or empty")
        else:
            thread = threading.Thread(target=self.load_apply_wallhaven_image, daemon=True)
            thread.start()

        return True

    def display_menu(self, button):
        menu = Gtk.Menu()
        menu.set_reserve_toggle_size(False)

        item = Gtk.MenuItem.new_with_label(self.voc["refresh"])
        item.connect("activate", self.apply_and_reset_timer)
        menu.append(item)

        if self.settings["interval"] > 0:
            if self.src_tag > 0:
                item = Gtk.MenuItem.new_with_label(self.voc['pause-refresh'])
                item.connect("activate", self.pause_refresh)
            else:
                item = Gtk.MenuItem.new_with_label(self.voc['resume-refresh'])
                item.connect("activate", self.resume_refresh)
            menu.append(item)

        if self.settings["source"] == "wallhaven.cc":
            item = Gtk.MenuItem.new_with_label(self.voc["image-info"])
            item.connect("activate", self.display_image_info_window)
            menu.append(item)

            item = Gtk.MenuItem.new_with_label(self.voc["random-wallpaper-save"])
            item.connect("activate", self.save_wallpaper)
            menu.append(item)

        menu.show_all()
        menu.popup_at_widget(self, Gdk.Gravity.NORTH, Gdk.Gravity.SOUTH, None)

        on_leave_notify_event(button, None)

    def pause_refresh(self, item):
        if self.src_tag > 0:
            GLib.Source.remove(self.src_tag)
            self.src_tag = 0

            image = Gtk.Image()
            update_image(image, "wallpaper", self.settings["icon-size"], self.icons_path)
            self.set_image(image)

    def resume_refresh(self, item):
        self.src_tag = GLib.timeout_add_seconds(self.settings["interval"] * 60, self.apply_wallpaper, None)

        image = Gtk.Image()
        update_image(image, "wallpaper-refresh", self.settings["icon-size"], self.icons_path)
        self.set_image(image)

    def apply_and_reset_timer(self, btn):
        self.apply_wallpaper(None)
        if self.settings["interval"] > 0:
            GLib.Source.remove(self.src_tag)
            self.src_tag = GLib.timeout_add_seconds(self.settings["interval"] * 60, self.apply_wallpaper, None)

    def display_image_info_window(self, item):
        w = ImageInfoWindow(self.image_info, self.voc)

    def save_wallpaper(self, item):
        info = load_json(self.wallpaper_info_path)
        output_file_name = f"wallhaven-{info['id']}.jpg"
        save_path = self.settings["save-path"] if self.settings["save-path"] else os.getenv("HOME")
        try:
            msg = f"{self.voc['saved-to']} {save_path}"
            copyfile(self.wallpaper_path, os.path.join(save_path, output_file_name))
            subprocess.Popen(f"notify-send '{output_file_name}' '{msg}' -i preferences-desktop-wallpaper", shell=True)
        except Exception as e:
            eprint(f"Failed saving: {os.path.join(save_path, output_file_name)}: {e}")


class ImageInfoWindow(Gtk.Window):
    def __init__(self, image_info, voc):
        Gtk.Window.__init__(self, type_hint=Gdk.WindowTypeHint.NORMAL)
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "nwg-panel")
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)

        self.connect("key-release-event", self.handle_keyboard)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(vbox)

        lbl = Gtk.Label()
        lbl.set_markup(f"<b>{voc['random-wallhaven-wallpaper']}</b>")
        vbox.pack_start(lbl, False, False, 6)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(hbox, False, False, 6)

        lines = ""
        for key in image_info:
            value = image_info[key]
            # nested dicts
            if isinstance(value, dict):
                l = ""
                for k in value:
                    l += f"\n\t{str(value[k])}"
                value = l
            if key == "url" or key == "short_url" or key == "path":
                value = f"<a href='{value}'>{value}</a>"
            line = f"<b>{key}</b>: {value}"
            lines += f"{line}\n"

        lbl = Gtk.Label()
        lbl.set_markup(lines)

        hbox.pack_start(lbl, False, False, 12)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(hbox, False, False, 6)
        btn = Gtk.Button()
        btn.set_label(voc["close"])
        btn.connect("clicked", self.quit)
        hbox.pack_end(btn, False, False, 6)

        self.show_all()

    def handle_keyboard(self, widget, event):
        if event.type == Gdk.EventType.KEY_RELEASE and event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def quit(self, btn):
        self.destroy()
