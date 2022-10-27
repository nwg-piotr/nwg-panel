#!/usr/bin/env python3

import threading
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from nwg_panel.tools import check_key, get_icon_name, update_image
import nwg_panel.common


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
            "icon-size": 16,
            "angle": 0.0
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        if settings["angle"] != 0.0:
            self.set_orientation(Gtk.Orientation.VERTICAL)

    def check_scratchpad(self, tree):
        content = []

        scratchpad = tree.find_named('__i3_scratch')
        leaves = scratchpad[0].floating_nodes

        for node in leaves:
            aid = node.app_id if node.app_id else node.window_class
            if aid:
                pid = node.pid
                if node.app_id:
                    icon = get_icon_name(node.app_id)
                elif node.window_class:
                    icon = get_icon_name(node.window_class)
                else:
                    icon = "icon-missing"

                item = {"aid": aid, "pid": pid, "icon": icon, "name": node.name, "con_id": node.id}
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
                eb.connect("button-press-event", self.on_button_press, item["pid"], item["con_id"])
                if item["name"]:
                    eb.set_tooltip_text(item["name"])
                self.pack_start(eb, False, False, 3)

        self.show_all()

    def on_button_press(self, eb, e, pid, con_id):
        if con_id in nwg_panel.common.scratchpad_cons:
            # If moved to scratchpad with the SwayTaskbar context menu, we have stored
            # the workspace number and floating state. Let's restore them.
            item = nwg_panel.common.scratchpad_cons[con_id]

            if "workspace" in item:
                if item["workspace"]:
                    # move to original workspace
                    cmd = "[con_id=\"{}\"] move to workspace number {}".format(con_id, item["workspace"])
                    self.i3.command(cmd)

            if "floating_con" in item:
                # restore floating state
                if item["floating_con"]:
                    cmd = "[con_id=\"{}\"] floating enable".format(con_id)
                else:
                    cmd = "[con_id=\"{}\"] floating disable".format(con_id)
                self.i3.command(cmd)

            # focus restored con
            cmd = "[con_id=\"{}\"] focus".format(con_id)
            self.i3.command(cmd)

        else:
            # If moved to scratchpad in another way, we have no info on WS number and floating state.
            # Let's just show the item.
            cmd = "[pid={}] scratchpad show".format(pid)
            self.i3.command(cmd)

    def refresh(self, tree):
        thread = threading.Thread(target=self.check_scratchpad(tree))
        thread.daemon = True
        thread.start()

        return True
