#!/usr/bin/env python3
import json
import os
import socket
import subprocess

from gi.repository import Gtk, Gdk, GdkPixbuf

from nwg_panel.tools import check_key, get_icon_name, update_image, get_config_dir, temp_dir, eprint
import nwg_panel.common


def hyprctl(cmd):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect("/tmp/hypr/{}/.socket.sock".format(os.getenv("HYPRLAND_INSTANCE_SIGNATURE")))

    s.send(cmd.encode("utf-8"))
    output = s.recv(8192).decode('utf-8')
    s.close()

    return output


class HyprlandTaskbar(Gtk.Box):
    def __init__(self, settings, position, display_name="", icons_path=""):
        self.position = position
        self.icons_path = icons_path
        check_key(settings, "workspaces-spacing", 0)
        check_key(settings, "image-size", 16)
        check_key(settings, "task-padding", 0)
        check_key(settings, "all-workspaces", True)
        check_key(settings, "all-outputs", False)
        check_key(settings, "mark-xwayland", True)
        check_key(settings, "name-max-len", 15)
        check_key(settings, "angle", 0.0)

        self.monitors = None
        self.mon_id2name = {}
        self.clients = None
        self.ws_nums = []
        self.workspaces = {}

        self.cache_file = os.path.join(temp_dir(), "nwg-scratchpad")

        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=settings["workspaces-spacing"])
        self.settings = settings
        if self.settings["angle"] != 0.0:
            self.set_orientation(Gtk.Orientation.VERTICAL)

        self.display_name = display_name

        self.list_monitors()
        self.refresh()
        self.ws_box = None

    def list_monitors(self):
        output = hyprctl("j/monitors")
        self.monitors = json.loads(output)
        for m in self.monitors:
            self.mon_id2name[m["id"]] = m["name"]
        print("monitors: {}".format(self.mon_id2name))

    def list_workspaces(self):
        output = hyprctl("j/workspaces")
        ws = json.loads(output)
        self.ws_nums = []
        self.workspaces = {}
        for item in ws:
            self.ws_nums.append(item["id"])
            self.workspaces[item["id"]] = item
        self.ws_nums.sort()

    def list_clients(self):
        output = hyprctl("j/clients")
        all_clients = json.loads(output)
        self.clients = []
        for c in all_clients:
            if c["monitor"] >= 0:
                if (self.mon_id2name[c["monitor"]] == self.display_name) or self.settings["all-outputs"]:
                    self.clients.append(c)

    def refresh(self):
        self.list_workspaces()
        self.list_clients()
        for item in self.get_children():
            item.destroy()
        self.build_box()

    def build_box(self):
        eprint(">> buildbox")
        for ws_num in self.ws_nums:
            ws_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
            self.pack_start(ws_box, False, False, 0)
            if self.workspaces[ws_num]["monitor"] == self.display_name or self.settings["all-outputs"]:
                lbl = Gtk.Label.new("{}:".format(self.workspaces[ws_num]["name"]))
                ws_box.pack_start(lbl, False, False, 6)
                cl_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
                ws_box.pack_start(cl_box, False, False, 0)
                for client in self.clients:
                    if client["workspace"]["id"] == ws_num:
                        client_box = ClientBox(self.settings, client, self.position, self.icons_path)
                        cl_box.pack_start(client_box, False, False, 3)

        self.show_all()


def on_enter_notify_event(widget, event):
    widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
    widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)


def on_leave_notify_event(widget, event):
    widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
    widget.unset_state_flags(Gtk.StateFlags.SELECTED)


class ClientBox(Gtk.EventBox):
    def __init__(self, settings, client, position, icons_path):
        self.position = position
        self.settings = settings
        self.address = client["address"]
        self.icons_path = icons_path
        Gtk.EventBox.__init__(self)
        self.box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, spacing=0)
        if settings["angle"] != 0.0:
            self.box.set_orientation(Gtk.Orientation.VERTICAL)
        self.add(self.box)

        self.connect('enter-notify-event', on_enter_notify_event)
        self.connect('leave-notify-event', on_leave_notify_event)
        self.connect('button-press-event', self.on_click, client, self.box)

        icon_name = client["class"]

        image = Gtk.Image()
        icon_theme = Gtk.IconTheme.get_default()
        try:
            # This should work if your icon theme provides the icon, or if it's placed in /usr/share/pixmaps
            pixbuf = icon_theme.load_icon(icon_name, self.settings["image-size"],
                                          Gtk.IconLookupFlags.FORCE_SIZE)
            image.set_from_pixbuf(pixbuf)
        except:
            # If the above fails, let's search .desktop files to find the icon name
            icon_from_desktop = get_icon_name(icon_name)
            if icon_from_desktop:
                # trim extension, if given and the definition is not a path
                if "/" not in icon_from_desktop and len(icon_from_desktop) > 4 and icon_from_desktop[
                    -4] == ".":
                    icon_from_desktop = icon_from_desktop[:-4]

                if "/" not in icon_from_desktop:
                    update_image(image, icon_from_desktop, self.settings["image-size"], self.icons_path)
                else:
                    try:
                        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_from_desktop,
                                                                        self.settings["image-size"],
                                                                        self.settings["image-size"])
                    except:
                        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                            os.path.join(get_config_dir(), "icons_light/icon-missing.svg"),
                            self.settings["image-size"],
                            self.settings["image-size"])
                    image.set_from_pixbuf(pixbuf)

        self.box.pack_start(image, False, False, 4)

        lbl = Gtk.Label()
        name = client["title"][:24]
        if settings["mark-xwayland"] and client["xwayland"]:
            name = "X|" + name
        lbl.set_text(name)
        self.box.pack_start(lbl, False, False, 6)

    def on_click(self, widget, event, client, popup_at_widget):
        if event.button == 1:
            eprint(hyprctl("dispatch focuswindow address:{}".format(self.address)))
        if event.button == 3:
            menu = self.context_menu(client)
            menu.show_all()
            if self.position == "bottom":
                menu.popup_at_widget(popup_at_widget, Gdk.Gravity.SOUTH, Gdk.Gravity.NORTH, None)
            else:
                menu.popup_at_widget(popup_at_widget, Gdk.Gravity.NORTH, Gdk.Gravity.SOUTH, None)

    def context_menu(self, client):
        menu = Gtk.Menu()
        menu.set_reserve_toggle_size(False)

        # Move to workspace
        for i in range(10):
            hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
            img = Gtk.Image()
            update_image(img, "go-right", 16, self.icons_path)
            hbox.pack_start(img, True, True, 0)
            lbl = Gtk.Label.new(str(i + 1))
            hbox.pack_start(lbl, False, False, 0)
            item = Gtk.MenuItem()
            item.add(hbox)
            item.connect("activate", self.movetoworkspace, i + 1)
            item.set_tooltip_text("movetoworkspace")
            menu.append(item)

        # Toggle floating
        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        img = Gtk.Image()
        update_image(img, "view-paged-symbolic", 16, self.icons_path)
        hbox.pack_start(img, True, True, 0)
        img = Gtk.Image()
        update_image(img, "view-dual-symbolic", 16, self.icons_path)
        hbox.pack_start(img, True, True, 0)
        item = Gtk.MenuItem()
        item.add(hbox)
        item.connect("activate", self.toggle_floating)
        item.set_tooltip_text("togglefloating")
        menu.append(item)

        # Fullscreen
        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        img = Gtk.Image()
        update_image(img, "view-fullscreen", 16, self.icons_path)
        hbox.pack_start(img, True, True, 0)
        item = Gtk.MenuItem()
        item.add(hbox)
        item.connect("activate", self.fullscreen)
        item.set_tooltip_text("fullscreen")
        menu.append(item)

        # Pin
        if client["floating"]:
            hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
            img = Gtk.Image()
            update_image(img, "pin", 16, self.icons_path)
            hbox.pack_start(img, True, True, 0)
            item = Gtk.MenuItem()
            item.add(hbox)
            item.connect("activate", self.pin)
            item.set_tooltip_text("pin")
            menu.append(item)

        # Close
        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        img = Gtk.Image()
        update_image(img, "gtk-close", 16, self.icons_path)
        hbox.pack_start(img, True, True, 0)
        item = Gtk.MenuItem()
        item.add(hbox)
        item.connect("activate", self.close, self.address)
        item.set_tooltip_text("closewindow")
        menu.append(item)

        return menu

    def close(self, *args):
        eprint(hyprctl("dispatch closewindow address:{}".format(self.address)))

    def toggle_floating(self, *args):
        eprint(hyprctl("dispatch togglefloating address:{}".format(self.address)))

    def fullscreen(self, *args):
        eprint(hyprctl("dispatch fullscreen address:{}".format(self.address)))

    def pin(self, *args):
        eprint(hyprctl("dispatch pin address:{}".format(self.address)))

    def movetoworkspace(self, menuitem, ws_num):
        eprint(hyprctl("dispatch movetoworkspace {},address:{}".format(ws_num, self.address)))
