#!/usr/bin/env python3

from gi.repository import Gtk, Gdk, GdkPixbuf

from nwg_panel.tools import check_key, get_icon, update_image
import nwg_panel.common


class SwayTaskbar(Gtk.Box):
    def __init__(self, settings, i3, position, display_name=""):
        self.position = position
        check_key(settings, "workspaces-spacing", 0)
        check_key(settings, "image-size", 16)
        check_key(settings, "workspace-menu", [1, 2, 3, 4, 5, 6, 7, 8])
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=settings["workspaces-spacing"])
        self.settings = settings
        self.display_name = display_name
        self.i3 = i3
        self.displays_tree = self.list_tree()
        self.build_box()
        self.ipc_data = {}
        self.ws_box = None

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
            for desc in display.descendants():
                if desc.type == "workspace":
                    self.ws_box = WorkspaceBox(desc, self.settings)
                    for con in desc.descendants():
                        if con.name or con.app_id:
                            win_box = WindowBox(con, self.settings, self.position)
                            self.ws_box.pack_start(win_box, False, False, 0)
                    self.pack_start(self.ws_box, False, False, 0)
        self.show_all()

    def refresh(self):
        for item in self.get_children():
            item.destroy()
        self.build_box()


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
    def __init__(self, con, settings, position):
        self.position = position
        self.settings = settings
        Gtk.EventBox.__init__(self)
        check_key(settings, "task-spacing", 0)
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
        self.connect('button-press-event', self.on_click, self.box)
        self.add_events(Gdk.EventMask.SCROLL_MASK)
        self.connect('scroll-event', self.on_scroll)

        check_key(settings, "show-app-icon", True)
        if settings["show-app-icon"]:
            name = con.app_id if con.app_id else con.window_class

            icon_from_desktop = get_icon(name)
            if icon_from_desktop:
                if "/" not in icon_from_desktop and not icon_from_desktop.endswith(
                        ".svg") and not icon_from_desktop.endswith(".png"):
                    image = Gtk.Image()
                    update_image(image, icon_from_desktop, settings["image-size"])
                else:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_from_desktop, settings["image-size"],
                                                                    settings["image-size"])
                    image = Gtk.Image.new_from_pixbuf(pixbuf)

                self.box.pack_start(image, False, False, 4)
            else:
                image = Gtk.Image()
                update_image(image, name, settings["image-size"])
                self.box.pack_start(image, False, False, 4)

        if con.name:
            check_key(settings, "name-max-len", 10)
            name = con.name[:settings["name-max-len"]] if len(con.name) > settings["name-max-len"] else con.name
            label = Gtk.Label(name)
            self.box.pack_start(label, False, False, 0)

        check_key(settings, "show-layout", True)
        if settings["show-layout"] and con.parent.layout:
            if con.parent.layout == "splith":
                image = Gtk.Image()
                update_image(image, "go-next", 16)
            elif con.parent.layout == "splitv":
                image = Gtk.Image()
                update_image(image, "go-down", 16)
            elif con.parent.layout == "tabbed":
                image = Gtk.Image()
                update_image(image, "view-dual", 16)
            elif con.parent.layout == "stacked":
                image = Gtk.Image()
                update_image(image, "view-paged", 16)
            else:
                image = Gtk.Image()
                update_image(image, "window-new", 16)

            self.box.pack_start(image, False, False, 4)

    def on_enter_notify_event(self, widget, event):
        self.get_style_context().set_state(Gtk.StateFlags.SELECTED)

    def on_leave_notify_event(self, widget, event):
        self.get_style_context().set_state(Gtk.StateFlags.NORMAL)

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
        for i in workspaces:
            ws_num = self.con_ws_num(self.con)
            if i != ws_num:
                text = "To workspace {}".format(i)
                item = Gtk.MenuItem(text)
                item.connect("activate", self.execute, i)
                menu.append(item)

        item = Gtk.SeparatorMenuItem()

        menu.append(item)
        item = Gtk.MenuItem("Toggle floating")
        item.connect("activate", self.floating_toggle)
        menu.append(item)

        item = Gtk.MenuItem("Kill")
        item.connect("activate", self.kill)
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

    def execute(self, item, ws_num):
        cmd = "[con_id=\"{}\"] move to workspace number {}".format(self.con.id, ws_num)
        nwg_panel.common.i3.command(cmd)

        cmd = "[con_id=\"{}\"] focus".format(self.con.id)
        nwg_panel.common.i3.command(cmd)

    def floating_toggle(self, item):
        cmd = "[con_id=\"{}\"] floating toggle".format(self.con.id)
        nwg_panel.common.i3.command(cmd)

    def kill(self, item):
        cmd = "[con_id=\"{}\"] kill".format(self.con.id)
        nwg_panel.common.i3.command(cmd)
