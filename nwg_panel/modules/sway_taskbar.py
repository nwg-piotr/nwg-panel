#!/usr/bin/env python3

from gi.repository import Gtk, GdkPixbuf

import sys
sys.path.append('../')

import nwg_panel.common
from nwg_panel.tools import check_key, get_icon


class SwayTaskbar(Gtk.Box):
    def __init__(self, settings, display_name=""):
        check_key(settings, "workspaces-spacing", 0)
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=settings["workspaces-spacing"])
        self.settings = settings
        self.display_name = display_name
        self.displays_tree = self.list_tree()
        self.build_box()
        self.ipc_data = {}

    def list_tree(self):
        i3_tree = nwg_panel.common.i3.get_tree()
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
            """print(display.type.upper(), display.name, display.rect.x, display.rect.y, display.rect.width,
                  display.rect.height)"""
            for desc in display.descendants():
                if desc.type == "workspace":
                    self.ws_box = WorkspaceBox(desc, self.settings)

                    for con in desc.descendants():
                        if con.name or con.app_id:
                            """print("    {} | name: {} layout: {} | app_id: {} | pid: {} | focused: {}"
                                  .format(con.type.upper(), con.name, con.parent.layout, con.app_id, con.pid,
                                          con.focused))"""
                            win_box = WindowBox(con, self.settings)
                            self.ws_box.pack_start(win_box, False, False, 0)
                    self.pack_start(self.ws_box, False, False, 0)
        self.show_all()
                    
    def refresh(self):
        if nwg_panel.common.i3.get_tree().ipc_data != self.ipc_data:
            for item in self.get_children():
                item.destroy()
            self.build_box()

            self.ipc_data = nwg_panel.common.i3.get_tree().ipc_data


class WorkspaceBox(Gtk.Box):
    def __init__(self, con, settings):
        self.con = con
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        check_key(settings, "workspace-buttons", False)
        if settings["workspace-buttons"]:
            widget = Gtk.Button.new_with_label("{}".format(con.num))
            widget.connect("clicked", self.on_click)
        else:
            widget = Gtk.Label("{}:".format(con.num))

        self.pack_start(widget, False, False, 4)
        
    def on_click(self, button):
        nwg_panel.common.i3.command("{} number {} focus".format(self.con.type, self.con.num))


class WindowBox(Gtk.EventBox):
    def __init__(self, con, settings):
        Gtk.EventBox.__init__(self)
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                           spacing=settings["task-spacing"] if settings["task-spacing"] else 0)
        self.add(self.box)
        self.con = con
        self.pid = con.pid
        
        self.old_name = ""

        if con.focused:
            self.box.set_property("name", "task-box-focused")
        else:
            self.box.set_property("name", "task-box")

        self.connect('enter-notify-event', self.on_enter_notify_event)
        self.connect('leave-notify-event', self.on_leave_notify_event)
        self.connect('button-press-event', self.on_click)

        if settings["show-app-icon"]:
            name = con.app_id if con.app_id else con.window_class

            icon_from_desktop = get_icon(name)
            if icon_from_desktop:
                if "/" not in icon_from_desktop and not icon_from_desktop.endswith(".svg") and not icon_from_desktop.endswith(".png"):
                    image = Gtk.Image.new_from_icon_name(icon_from_desktop, Gtk.IconSize.MENU)
                else:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_from_desktop, 16, 16)
                    image = Gtk.Image.new_from_pixbuf(pixbuf)

                self.box.pack_start(image, False, False, 4)
            else:
                image = Gtk.Image.new_from_icon_name(name, Gtk.IconSize.MENU)
                self.box.pack_start(image, False, False, 4)

        if con.name:
            check_key(settings, "name-max-len", 10)
            name = con.name[:settings["name-max-len"]] if len(con.name) > settings["name-max-len"] else con.name
            label = Gtk.Label(name)
            self.box.pack_start(label, False, False, 0)

        if settings["show-layout"] and con.parent.layout:
            if con.parent.layout == "splith":
                image = Gtk.Image.new_from_icon_name("go-next", Gtk.IconSize.MENU)
            elif con.parent.layout == "splitv":
                image = Gtk.Image.new_from_icon_name("go-down", Gtk.IconSize.MENU)
            elif con.parent.layout == "tabbed":
                image = Gtk.Image.new_from_icon_name("view-dual", Gtk.IconSize.MENU)
            elif con.parent.layout == "stacked":
                image = Gtk.Image.new_from_icon_name("view-paged", Gtk.IconSize.MENU)
            else:
                image = Gtk.Image.new_from_icon_name("window-new", Gtk.IconSize.MENU)
            
            self.box.pack_start(image, False, False, 4)

    def on_enter_notify_event(self, widget, event):
        self.get_style_context().set_state(Gtk.StateFlags.SELECTED)
        
    def on_leave_notify_event(self, widget, event):
        self.get_style_context().set_state(Gtk.StateFlags.NORMAL)

    def on_click(self, widget, event):
        if event.button == 3:
            cmd = "[con_id=\"{}\"] kill".format(self.con.id)
        else:
            cmd = "[con_id=\"{}\"] focus".format(self.con.id)
        nwg_panel.common.i3.command(cmd)