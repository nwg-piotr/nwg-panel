#!/usr/bin/env python3

import threading
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from nwg_panel.tools import check_key, get_icon, update_image


class Scratchpad(Gtk.Box):
    def __init__(self, i3, tree, settings, icons_path=""):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.settings = settings
        self.i3 = i3
        self.tree = tree
        self.content = []
        self.icons_path = icons_path

        defaults = {
            "css-name": "",
            "icon-size": 16
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

    def check_scratchpad(self, tree):
        content = []

        scratchpad = tree.find_named('__i3_scratch')
        leaves = scratchpad[0].floating_nodes

        for node in leaves:
            aid = node.app_id if node.app_id else node.window_class
            if aid:
                pid = node.pid
                if node.app_id:
                    icon = get_icon(node.app_id)
                elif node.window_class:
                    icon = get_icon(node.window_class)
                else:
                    icon = "icon-missing"

                item = {"aid": aid, "pid": pid, "icon": icon, "name": node.name}
                content.append(item)

        if content != self.content:
            self.content = content
            self.build_box()

    def build_box(self):
        for item in self.get_children():
            item.destroy()

        if len(self.content) > 0 and self.settings["css-name"]:
            self.set_property("name", self.settings["css-name"])
        else:
            self.set_property("name", None)

        for item in self.content:
            if item["icon"]:
                eb = Gtk.EventBox()
                image = Gtk.Image()
                update_image(image, item["icon"], self.settings["icon-size"], self.icons_path)
                eb.add(image)
                eb.connect("button-press-event", self.on_button_press, item["pid"])
                if item["name"]:
                    eb.set_tooltip_text(item["name"])
                self.pack_start(eb, False, False, 3)

        self.show_all()

    def on_button_press(self, eb, e, pid):
        cmd = "[pid={}] scratchpad show".format(pid)
        self.i3.command(cmd)

    def refresh(self, tree):
        thread = threading.Thread(target=self.check_scratchpad(tree))
        thread.daemon = True
        thread.start()

        return True
