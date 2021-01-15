#!/usr/bin/env python3

from gi.repository import Gtk

from i3ipc import Connection

from nwg_panel.tools import save_json

import os


class SwayWorkspaces(Gtk.Box):
    def __init__(self, display_name="", spacing=0):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)
        self.i3 = Connection()
        self.display_name = display_name
        self.displays_tree = self.list_tree()
        
        self.build_box()

    def list_tree(self):
        i3_tree = self.i3.get_tree()
        """
        display -> workspace -> window -> app_id
                                       -> parent_layout
                                       -> name
                                       -> pid
                                       -> con
                             -> window -> (...)
                -> workspace -> (...)
        display -> (...)
        """
        displays_tree = []
        if self.display_name:
            for item in i3_tree:
                if item.type == "output" and item.name == self.display_name:
                    displays_tree.append(item)
        else:
            for item in i3_tree:
                if item.type == "output" and not item.name.startswith("__"):
                    displays_tree.append(item)
                    
        # sort by x, y coordinates
        displays_tree = sorted(displays_tree, key=lambda d: (d.rect.x, d.rect.y))

        return displays_tree
    
    def build_box(self):
        self.displays_tree = self.list_tree()

        for display in self.displays_tree:
            print(display.type.upper(), display.name, display.rect.x, display.rect.y, display.rect.width,
                  display.rect.height)
            for desc in display.descendants():
                if desc.type == "workspace":
                    print("  ", desc.type.upper(), desc.num)
                    ws_box = WorkspaceBox(desc)

                    for con in desc.descendants():
                        if con.name or con.app_id:
                            print("    {} | name: {} layout: {} | app_id: {} | pid: {} | focused: {}"
                                  .format(con.type.upper(), con.name, con.parent.layout, con.app_id, con.pid,
                                          con.focused))
                            win_box = WindowBox(con)
                            ws_box.pack_start(win_box, False, False, 3)
                            
                    self.pack_start(ws_box, False, False, 0)
                    self.show_all()
                    
    def refresh(self):
        for item in self.get_children():
            item.destroy()
        self.build_box()


class WorkspaceBox(Gtk.Box):
    def __init__(self, con):
        self.con = con
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn = Gtk.Button.new_with_label("{}".format(con.num))
        btn.connect("clicked", self.on_click)
        self.pack_start(btn, False, False, 0)
        
    def on_click(self, button):
        print("Clicked!")
        self.con.command("focus")


class WindowBox(Gtk.Box):
    # con, icon: str, parent_layout: str, name: str, focused: bool
    def __init__(self, con):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.con = con
        self.pid = con.pid

        if con.focused:
            self.set_property("name", "window-box-focused")

        if con.app_id:
            image = Gtk.Image.new_from_icon_name(con.app_id, Gtk.IconSize.MENU)
            self.pack_start(image, False, False, 0)

        if con.name:
            name = con.name[:12] if len(con.name) > 12 else con.name
            label = Gtk.Label(name)
            self.pack_start(label, False, False, 4)

        if con.parent.layout:
            if con.parent.layout == "splith":
                image = Gtk.Image.new_from_icon_name("go-next", Gtk.IconSize.MENU)
            elif con.parent.layout == "splitv":
                image = Gtk.Image.new_from_icon_name("go-down", Gtk.IconSize.MENU)
            else:
                image = Gtk.Image.new_from_icon_name("window-new", Gtk.IconSize.MENU)
            self.pack_start(image, False, False, 0)
