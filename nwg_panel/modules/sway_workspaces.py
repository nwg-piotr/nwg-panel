#!/usr/bin/env python3

from gi.repository import Gtk, GdkPixbuf

import nwg_panel.common
from nwg_panel.tools import check_key, get_icon, update_image,load_autotiling


class SwayWorkspaces(Gtk.Box):
    def __init__(self, settings, i3, icons_path):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.settings = settings
        self.i3 = i3
        self.ws_num2box = {}
        self.ws_num2lbl = {}
        self.name_label = Gtk.Label("")
        self.win_id = ""
        self.icon = Gtk.Image()
        self.icons_path = icons_path
        self.autotiling = load_autotiling()
        self.build_box()

    def build_box(self):
        check_key(self.settings, "numbers", [1, 2, 3, 4, 5, 6, 7, 8])
        check_key(self.settings, "show-icon", True)
        check_key(self.settings, "image-size", 16)
        check_key(self.settings, "show-name", True)
        check_key(self.settings, "name-length", 40)
        check_key(self.settings, "mark-autotiling", True)
        check_key(self.settings, "mark-content", True)

        ws_num, win_name, win_id, non_empty = self.find_details()

        for num in self.settings["numbers"]:
            eb = Gtk.EventBox()
            eb.connect("enter_notify_event", self.on_enter_notify_event)
            eb.connect("leave_notify_event", self.on_leave_notify_event)
            eb.connect("button-press-event", self.on_click, num)
            self.pack_start(eb, False, False, 0)

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            eb.add(box)

            if self.settings["mark-autotiling"]:
                try:
                    at = int(num) in self.autotiling
                except:
                    at = False
                autotiling = "a" if at in self.autotiling else ""
                lbl = Gtk.Label("{}{}".format(autotiling, str(num)))
            else:
                lbl = Gtk.Label("{}".format(str(num)))
            
            self.ws_num2box[num] = eb
            self.ws_num2lbl[num] = lbl

            box.pack_start(lbl, False, False, 6)

            if num == str(ws_num):
                eb.set_property("name", "task-box-focused")
            else:
                eb.set_property("name", "task-box")

        if self.settings["show-icon"]:
            self.pack_start(self.icon, False, False, 6)

        if self.settings["show-name"]:
            self.pack_start(self.name_label, False, False, 0)
        
    def refresh(self):
        ws_num, win_name, win_id, non_empty = self.find_details()
        if ws_num > 0:
            for num in self.settings["numbers"]:
                # mark non-empty WS with a dot
                if self.settings["mark-content"]:
                    try:
                        int_num = int(num)
                    except:
                        int_num = 0
                    lbl = self.ws_num2lbl[num]
                    text = lbl.get_text()
                    if int_num in non_empty:
                        if not text.endswith("."):
                            text += "."
                            lbl.set_text(text)
                    else:
                        if text.endswith("."):
                            text = text[0:-1]
                            lbl.set_text(text)

                if num == str(ws_num):
                    self.ws_num2box[num].set_property("name", "task-box-focused")
                else:
                    self.ws_num2box[num].set_property("name", "task-box")

            if self.settings["show-icon"] and win_id != self.win_id:
                self.update_icon(win_id, win_name)
                self.win_id = win_id

        if self.settings["show-name"]:
            self.name_label.set_text(win_name)
    
    def update_icon(self, win_id, win_name):
        if win_id and win_name:
            icon_from_desktop = get_icon(win_id)
            if icon_from_desktop:
                if "/" not in icon_from_desktop and not icon_from_desktop.endswith(
                        ".svg") and not icon_from_desktop.endswith(".png"):
                    update_image(self.icon, icon_from_desktop, self.settings["image-size"], self.icons_path)
                else:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_from_desktop, self.settings["image-size"],
                                                                    self.settings["image-size"])
                    self.icon.set_from_pixbuf(pixbuf)
            else:
                image = Gtk.Image()
                update_image(image, win_id, self.settings["image-size"], self.icons_path)
            
            if not self.icon.get_visible():
                self.icon.show()
        else:
            if self.icon.get_visible():
                self.icon.hide()

    def find_details(self):
        tree = self.i3.get_tree()
        workspaces = self.i3.get_workspaces()
        ws_num = -1
        win_name = ""
        win_id = ""    # app_id if available, else window_class

        for ws in workspaces:
            if ws.focused:
                ws_num = ws.num
                break

        if self.settings["show-name"] or self.settings["show-icon"]:
            non_empty = []
            f = self.i3.get_tree().find_focused()
            if f.type == "con" and f.name and str(f.parent.workspace().num) in self.settings["numbers"]:
                win_name = f.name[:self.settings["name-length"]]
                
                if f.app_id:
                    win_id = f.app_id
                elif f.window_class:
                    win_id = f.window_class

            for item in tree.descendants():
                if item.type == "workspace":
                    # find non-empty workspaces
                    if self.settings["mark-content"]:
                        tasks_num = 0
                        for d in item.descendants():
                            if d.type == "con" and d.name:
                                tasks_num += 1
                        if tasks_num > 0:
                            non_empty.append(item.num)
                    
                    for node in item.floating_nodes:
                        if str(node.workspace().num) in self.settings["numbers"] and node.focused:
                            win_name = node.name

                            if node.app_id:
                                win_id = node.app_id
                            elif node.window_class:
                                win_id = node.window_class

        return ws_num, win_name, win_id, non_empty

    def on_click(self, w, e, num):
        nwg_panel.common.i3.command("workspace number {}".format(num))

    def on_enter_notify_event(self, widget, event):
        widget.get_style_context().set_state(Gtk.StateFlags.SELECTED)

    def on_leave_notify_event(self, widget, event):
        widget.get_style_context().set_state(Gtk.StateFlags.NORMAL)