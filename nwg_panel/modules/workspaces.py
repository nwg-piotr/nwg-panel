#!/usr/bin/env python3

from gi.repository import Gtk

from i3ipc import Connection

from nwg_panel.tools import save_json

import os


class SwayWorkspaces(Gtk.Box):
    def __init__(self, display_name="", spacing=0):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)
        self.display_name = display_name
        self.displays_tree = None  # displays -> workspaces -> windows
        self.list_tree()

    def list_tree(self):
        i3 = Connection()
        i3_tree = i3.get_tree()
        """
        display -> workspace -> window -> app_id
                                       -> name
                                       -> pid
                                       -> parent_layout
                             -> window -> (...)
                -> workspace -> (...)
        display -> (...)
        """
        self.displays_tree = []
        if self.display_name:
            for item in i3_tree:
                if item.type == "output" and item.name == self.display_name:
                    self.displays_tree.append(item)
        else:
            for item in i3_tree:
                if item.type == "output" and not item.name.startswith("__"):
                    self.displays_tree.append(item)
                    
        # sort displays by coordinates
        self.displays_tree = sorted(self.displays_tree, key=lambda d: (d.rect.x, d.rect.y))

        for display in self.displays_tree:
            print(display.type.upper(), display.name, display.rect.x, display.rect.y, display.rect.width, display.rect.height)
            for d in display.descendants():
                if d.type == "workspace":
                    print("  ", d.type.upper(), d.num)
                    for w in d.descendants():
                        if w.name or w.app_id:
                            print("    {} | name: {} layout: {} | app_id: {} | pid: {} | focused: {}"
                                  .format(w.type.upper(), w.name, w.parent.layout, w.app_id, w.pid, w.focused))
                            # w.command("focus")


class WorkspaceBox(Gtk.Box):
    def __init__(self, num):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
