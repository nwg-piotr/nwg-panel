#!/usr/bin/env python3
import json
import os
import subprocess

from gi.repository import Gtk, Gdk, GdkPixbuf

from nwg_panel.tools import check_key, get_icon_name, update_image, load_autotiling, get_config_dir, temp_dir, \
    save_json
import nwg_panel.common


class HyprlandTaskbar(Gtk.Box):
    def __init__(self, settings, position, display_name="", icons_path=""):
        self.position = position
        self.icons_path = icons_path
        check_key(settings, "workspaces-spacing", 0)
        check_key(settings, "image-size", 16)
        check_key(settings, "task-padding", 0)
        check_key(settings, "all-workspaces", True)
        check_key(settings, "mark-xwayland", True)
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
        # self.build_box()
        self.ws_box = None

    def list_monitors(self):
        output = subprocess.check_output("hyprctl -j monitors".split()).decode('utf-8')
        self.monitors = json.loads(output)
        for m in self.monitors:
            self.mon_id2name[m["id"]] = m["name"]
        print("monitors: {}".format(self.mon_id2name))

    def list_workspaces(self):
        output = subprocess.check_output("hyprctl -j workspaces".split()).decode('utf-8')
        ws = json.loads(output)
        self.ws_nums = []
        self.workspaces = {}
        for item in ws:
            self.ws_nums.append(item["id"])
            self.workspaces[item["id"]] = item

    def list_clients(self):
        output = subprocess.check_output("hyprctl -j clients".split()).decode('utf-8')
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
        self.build_box1()

    def build_box1(self):
        print("buildbox1")
        for n in self.ws_nums:
            ws_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
            self.pack_start(ws_box, False, False, 0)
            if self.workspaces[n]["monitor"] == self.display_name or self.settings["all-outputs"]:
                lbl = Gtk.Label.new(self.workspaces[n]["name"])
                ws_box.pack_start(lbl, False, False, 6)
                cl_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
                ws_box.pack_start(cl_box, False, False, 0)
                for c in self.clients:
                    if c["workspace"]["id"] == n:
                        lbl = Gtk.Label.new("{}>>{}".format(c["class"], c["title"][:20]))
                        cl_box.pack_start(lbl, False, False, 6)

        self.show_all()

    def list_tree(self):
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
            for item in self.tree:
                if item.type == "output" and item.name == self.display_name:
                    displays_tree.append(item)
        else:
            for item in self.tree:
                if item.type == "output" and not item.name.startswith("__"):
                    displays_tree.append(item)

        # sort by x, y coordinates
        displays_tree = sorted(displays_tree, key=lambda d: (d.rect.x, d.rect.y))

        return displays_tree

    def build_box(self):
        self.displays_tree = self.list_tree()
        all_workspaces = self.settings["all-workspaces"]

        for display in self.displays_tree:
            for desc in display.descendants():
                if desc.type == "workspace":
                    self.ws_box = WorkspaceBox(desc, self.settings, self.autotiling)
                    if all_workspaces or desc.find_focused() is not None:
                        for con in desc.descendants():
                            if con.name or con.app_id:
                                win_box = WindowBox(self.tree, con, self.settings, self.position, self.icons_path,
                                                    self.cache_file, floating=con in desc.floating_nodes)
                                self.ws_box.pack_start(win_box, False, False, self.settings["task-padding"])
                    self.pack_start(self.ws_box, False, False, 0)
        self.show_all()

    # def refresh(self, tree):
    #     self.tree = tree
    #     for item in self.get_children():
    #         item.destroy()
    #     self.build_box()


class WorkspaceBox(Gtk.Box):
    def __init__(self, con, settings, autotiling):
        self.con = con
        at_indicator = "a" if con.num in autotiling else ""
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        if settings["angle"] != 0.0:
            self.set_orientation(Gtk.Orientation.VERTICAL)

        check_key(settings, "workspace-buttons", False)
        if settings["workspace-buttons"]:
            widget = Gtk.Button.new_with_label("{}{}".format(at_indicator, con.num))
            widget.connect("clicked", self.on_click)
        else:
            widget = Gtk.Label("{}{}:".format(at_indicator, con.num))
            widget.set_angle(settings["angle"])

        self.pack_start(widget, False, False, 4)

    def on_click(self, button):
        nwg_panel.common.i3.command("{} number {} focus".format(self.con.type, self.con.num))


class WindowBox(Gtk.EventBox):
    def __init__(self, tree, con, settings, position, icons_path, cache_file, floating=False):
        self.position = position
        self.settings = settings
        Gtk.EventBox.__init__(self)
        self.box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, spacing=0)
        if settings["angle"] != 0.0:
            self.box.set_orientation(Gtk.Orientation.VERTICAL)
        self.add(self.box)
        self.con = con
        self.pid = con.pid
        self.icons_path = icons_path
        self.tree = tree
        self.cache_file = cache_file

        self.old_name = ""

        if con.focused:
            self.box.set_property("name", "task-box-focused")
        else:
            self.box.set_property("name", "task-box")

        self.connect('enter-notify-event', self.on_enter_notify_event)
        self.connect('leave-notify-event', self.on_leave_notify_event)
        self.connect('button-press-event', self.on_click, self.box)
        self.add_events(Gdk.EventMask.SCROLL_MASK)
        self.connect('scroll-event', self.on_scroll)

        check_key(settings, "show-app-icon", True)
        if settings["show-app-icon"]:
            name = con.app_id if con.app_id else con.window_class

            image = Gtk.Image()
            icon_theme = Gtk.IconTheme.get_default()
            try:
                # This should work if your icon theme provides the icon, or if it's placed in /usr/share/pixmaps
                pixbuf = icon_theme.load_icon(name, settings["image-size"], Gtk.IconLookupFlags.FORCE_SIZE)
                image.set_from_pixbuf(pixbuf)
            except:
                # If the above fails, let's search .desktop files to find the icon name
                icon_from_desktop = get_icon_name(name)
                if icon_from_desktop:
                    # trim extension, if given and the definition is not a path
                    if "/" not in icon_from_desktop and len(icon_from_desktop) > 4 and icon_from_desktop[-4] == ".":
                        icon_from_desktop = icon_from_desktop[:-4]

                    if "/" not in icon_from_desktop:
                        update_image(image, icon_from_desktop, settings["image-size"], icons_path)
                    else:
                        try:
                            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_from_desktop, settings["image-size"],
                                                                            settings["image-size"])
                        except:
                            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                                os.path.join(get_config_dir(), "icons_light/icon-missing.svg"), settings["image-size"],
                                settings["image-size"])
                        image.set_from_pixbuf(pixbuf)

            self.box.pack_start(image, False, False, 4)

        if con.name:
            check_key(settings, "show-app-name", True)
            check_key(settings, "name-max-len", 20)
            name = con.name[:settings["name-max-len"]] if len(con.name) > settings["name-max-len"] else con.name
            if settings["mark-xwayland"] and not con.app_id:
                name = "X|" + name
            if settings["show-app-name"]:
                check_key(settings, "name-max-len", 10)
                label = Gtk.Label(name)
                label.set_angle(settings["angle"])
                self.box.pack_start(label, False, False, 0)
            else:
                self.set_tooltip_text(name)

        check_key(settings, "show-layout", True)

        if settings["show-layout"] and con.parent.layout:
            if con.parent.layout == "splith":
                image = Gtk.Image()
                update_image(image, "go-next-symbolic", 16, icons_path)
            elif con.parent.layout == "splitv":
                image = Gtk.Image()
                update_image(image, "go-down-symbolic", 16, icons_path)
            elif con.parent.layout == "tabbed":
                image = Gtk.Image()
                update_image(image, "view-dual-symbolic", 16, icons_path)
            elif con.parent.layout == "stacked":
                image = Gtk.Image()
                update_image(image, "view-paged-symbolic", 16, icons_path)

            if floating:
                image = Gtk.Image()
                update_image(image, "window-pop-out-symbolic", 16, icons_path)

            self.box.pack_start(image, False, False, 4)

    def on_enter_notify_event(self, widget, event):
        widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
        widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)

    def on_leave_notify_event(self, widget, event):
        widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
        widget.unset_state_flags(Gtk.StateFlags.SELECTED)

    def on_click(self, widget, event, at_widget):
        if event.button == 1:
            cmd = "[con_id=\"{}\"] focus".format(self.con.id)
            nwg_panel.common.i3.command(cmd)
        if event.button == 3:
            menu = self.context_menu(self.settings["workspace-menu"])
            menu.show_all()
            if self.position == "bottom":
                menu.popup_at_widget(at_widget, Gdk.Gravity.SOUTH, Gdk.Gravity.NORTH, None)
            else:
                menu.popup_at_widget(at_widget, Gdk.Gravity.NORTH, Gdk.Gravity.SOUTH, None)

    def on_scroll(self, widget, event):
        cmd = "[con_id=\"{}\"] focus".format(self.con.id)
        nwg_panel.common.i3.command(cmd)
        if event.direction == Gdk.ScrollDirection.UP:
            cmd = "[con_id=\"{}\"] layout toggle tabbed stacking splitv splith".format(self.con.id)
            nwg_panel.common.i3.command(cmd)
        elif event.direction == Gdk.ScrollDirection.DOWN:
            cmd = "[con_id=\"{}\"] layout toggle splith splitv stacking tabbed".format(self.con.id)
            nwg_panel.common.i3.command(cmd)

    def context_menu(self, workspaces):
        menu = Gtk.Menu()
        menu.set_reserve_toggle_size(False)
        # Numbers have been converted to strings by mistake (config.py). Reverting this would be a breaking change,
        # so let's accept both numbers and strings.
        for i in workspaces:
            ws_num = self.con_ws_num(self.con)
            if str(i) != str(ws_num):
                hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
                img = Gtk.Image()
                update_image(img, "go-next-symbolic", 16, self.icons_path)
                hbox.pack_start(img, True, True, 0)
                label = Gtk.Label(str(i))
                hbox.pack_start(label, True, True, 0)
                item = Gtk.MenuItem()
                item.add(hbox)
                item.connect("activate", self.move_to_workspace, i)
                item.set_tooltip_text("move to workspace number {}".format(i))
                menu.append(item)

        # Move to scratchpad
        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        img = Gtk.Image()
        update_image(img, "go-next-symbolic", 16, self.icons_path)
        hbox.pack_start(img, True, True, 0)
        img = Gtk.Image()
        update_image(img, "edit-paste", 16, self.icons_path)
        hbox.pack_start(img, True, True, 0)
        item = Gtk.MenuItem()
        item.add(hbox)
        item.connect("activate", self.move_scratchpad)
        item.set_tooltip_text('move scratchpad ("minimize")')
        menu.append(item)

        item = Gtk.SeparatorMenuItem()

        menu.append(item)

        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        img = Gtk.Image()
        update_image(img, "view-paged-symbolic", 16, self.icons_path)
        hbox.pack_start(img, True, True, 0)
        img = Gtk.Image()
        update_image(img, "view-dual-symbolic", 16, self.icons_path)
        hbox.pack_start(img, True, True, 0)
        item = Gtk.MenuItem()
        item.add(hbox)
        item.connect("activate", self.floating_toggle)
        item.set_tooltip_text("floating toggle")
        menu.append(item)

        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        img = Gtk.Image()
        update_image(img, "window-close-symbolic", 16, self.icons_path)
        hbox.pack_start(img, True, True, 0)
        item = Gtk.MenuItem()
        item.add(hbox)
        item.connect("activate", self.kill)
        item.set_tooltip_text("kill")
        menu.append(item)

        return menu

    def con_ws_num(self, con):
        ws_num = 0
        leave = con
        parent = con.parent
        while parent.type != "root":
            parent = leave.parent
            leave = parent
            if leave.type == "workspace":
                ws_num = leave.num

        return ws_num

    def move_to_workspace(self, item, ws_num):
        cmd = "[con_id=\"{}\"] move to workspace number {}".format(self.con.id, ws_num)
        nwg_panel.common.i3.command(cmd)

        cmd = "[con_id=\"{}\"] focus".format(self.con.id)
        nwg_panel.common.i3.command(cmd)

    def move_scratchpad(self, item):
        # d dictionary is to remember con workspace number, floating state and parent output name,
        # to bring it back from scratchpad to its original place, in original state.
        d = {"floating_con": self.con.type == "floating_con"}
        for ws in self.tree.workspaces():
            if ws.find_by_id(self.con.id):
                d["workspace"] = ws.num
                break

        # We'll need the output name to (optionally) filter the Scratchpad module icons by the panel output name.
        d["output"] = self.con_parent_output_name(self.con)

        # key must not be a number, as json keys are always strings, and we will try to restore this dict from cache
        nwg_panel.common.scratchpad_cons[str(self.con.id)] = d

        # save to the cache file, for the information to survive panel restarts
        save_json(nwg_panel.common.scratchpad_cons, self.cache_file)

        cmd = "[con_id=\"{}\"] move to scratchpad".format(self.con.id)
        nwg_panel.common.i3.command(cmd)

    def floating_toggle(self, item):
        cmd = "[con_id=\"{}\"] floating toggle".format(self.con.id)
        nwg_panel.common.i3.command(cmd)

    def kill(self, item):
        cmd = "[con_id=\"{}\"] kill".format(self.con.id)
        nwg_panel.common.i3.command(cmd)

    def con_parent_output_name(self, con):
        p = con.parent
        if p:
            if p.type == "output":
                return p.name
            else:
                return self.con_parent_output_name(p)

        return None
