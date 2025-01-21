#!/usr/bin/env python3

from gi.repository import Gtk, Gdk

from nwg_panel.tools import hyprctl, update_image, update_image_fallback_desktop, is_hyprland_workspace_rule_valid, h_list_workspace_rules, h_list_monitors, h_list_workspaces


class HyprlandTaskbar(Gtk.Box):
    def __init__(self, settings, position, monitors, workspaces, clients, activewindow, display_name="", icons_path=""):
        defaults = {
            "name-max-len": 24,
            "image-size": 16,
            "workspaces-spacing": 0,
            "client-padding": 0,
            "show-app-icon": True,
            "show-app-name": True,
            "show-workspace": True,
            "all-workspaces": True,
            "show-app-name-special": False,
            "show-layout": True,
            "all-outputs": False,
            "mark-xwayland": True,
            "angle": 0.0
        }
        for key in defaults:
            if key not in settings:
                settings[key] = defaults[key]
        self.settings = settings

        self.position = position
        self.display_name = display_name
        self.icons_path = icons_path

        self.monitors = None
        self.mon_id2name = {}
        self.active_workspaces = None
        self.clients = None
        self.ws_nums = None
        self.workspaces = None
        self.activewindow = None

        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=settings["workspaces-spacing"])
        if self.settings["angle"] != 0.0:
            self.set_orientation(Gtk.Orientation.VERTICAL)

        self.refresh(monitors, workspaces, clients, activewindow)

    def parse_monitors(self, monitors):
        self.monitors = monitors
        self.active_workspaces = []
        for m in self.monitors:
            self.mon_id2name[m["id"]] = m["name"]
            self.active_workspaces.append(m["activeWorkspace"]["id"])

    def parse_workspaces(self, ws):
        self.ws_nums = []
        self.workspaces = {}
        for item in ws:
            self.ws_nums.append(item["id"])
            self.workspaces[item["id"]] = item
        self.ws_nums.sort()

    # def parse_clients(self, all_clients):
    #     self.clients = []
    #     for c in all_clients:
    #         if c["monitor"] >= 0:
    #             if (self.mon_id2name[c["monitor"]] == self.display_name) or self.settings["all-outputs"]:
    #               self.clients.append(c)

    def refresh(self, monitors, workspaces, clients, activewindow):
        
        self.parse_monitors(monitors)
        if self.settings["all-workspaces"]:
            self.parse_workspaces(workspaces)
        else:
            # parsing active_ws
            if self.settings["all-outputs"]:
                current_mons = [m for m in monitors]
            else:
                current_mons = [m for m in monitors if m["name"] == self.display_name]
            # active workspace on the current monitor is what we want
            active_workspaces = []
            for mon in current_mons:
                for ws in workspaces:
                    if mon['activeWorkspace']["id"] == ws["id"]:
                        active_workspaces.append(ws)
            self.ws_nums = [active_ws["id"] for active_ws in active_workspaces]
            self.workspaces = {active_ws["id"]: active_ws for active_ws in active_workspaces}
        
        # Turned off due to https://github.com/hyprwm/Hyprland/issues/2413
        # self.parse_clients(clients)
        self.clients = clients
        self.activewindow = activewindow
        for item in self.get_children():
            item.destroy()
        self.build_box(workspaces)

    def create_workspace_label(self, ws_num):
        lbl = Gtk.Label()
        if ws_num in self.active_workspaces:
            lbl.set_markup("<u>{}</u>:".format(self.workspaces[ws_num]["name"]))
        else:
            lbl.set_text("{}:".format(self.workspaces[ws_num]["name"]))
        return lbl

    def build_box(self, workspaces):
        # eprint(">> buildbox")
        for ws_num in self.ws_nums:
            ws_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
            if self.settings["angle"] != 0.0:
                ws_box.set_orientation(Gtk.Orientation.VERTICAL)
            self.pack_start(ws_box, False, False, 0)
            if self.workspaces[ws_num]["monitor"] == self.display_name or self.settings["all-outputs"]:
                eb = Gtk.EventBox()
                # if self.settings["workspace-clickable"]:
                #     eb.connect('enter-notify-event', on_enter_notify_event)
                #     eb.connect('leave-notify-event', on_leave_notify_event)
                #     eb.connect('button-press-event', self.on_ws_click, ws_num)

                if self.settings["show-workspace"]:
                    ws_box.pack_start(eb, False, False, 6)
                    eb.add(self.create_workspace_label(ws_num))
                cl_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
                ws_box.pack_start(cl_box, False, False, 0)
                for client in self.clients:
                    # if client["title"] prevents from creation of ghost client boxes
                    if client["title"] and client["workspace"]["id"] == ws_num:
                        client_box = ClientBox(self.settings, client, self.position, self.icons_path, workspaces, self.display_name)
                        if self.activewindow and client["address"] == self.activewindow["address"]:
                            client_box.box.set_property("name", "task-box-focused")
                        else:
                            client_box.box.set_property("name", "task-box")
                        cl_box.pack_start(client_box, False, False, self.settings["client-padding"])

        self.show_all()

    def on_ws_click(self, widget, event, ws_num):
        hyprctl("dispatch workspace name:{}".format(ws_num))


def on_enter_notify_event(widget, event):
    widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
    widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)


def on_leave_notify_event(widget, event):
    widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
    widget.unset_state_flags(Gtk.StateFlags.SELECTED)


class ClientBox(Gtk.EventBox):
    def __init__(self, settings, client, position, icons_path, workspaces, display_name):
        self.position = position
        self.settings = settings
        self.address = client["address"]
        self.icons_path = icons_path
        self.display_name = display_name
        ### read workspace rules
        self.workspace_rules = [rule for rule in h_list_workspace_rules() if is_hyprland_workspace_rule_valid(rule)]
        self.workspace_ids_for_context_menu = self.sorted_workspace_ids()

        Gtk.EventBox.__init__(self)
        self.box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, spacing=0)
        if settings["angle"] != 0.0:
            self.box.set_orientation(Gtk.Orientation.VERTICAL)
        self.add(self.box)

        self.connect('enter-notify-event', on_enter_notify_event)
        self.connect('leave-notify-event', on_leave_notify_event)
        if client["workspace"]["name"] == "special":
            self.connect('button-release-event', self.on_special)
        else:
            self.connect('button-release-event', self.on_click, client, self.box)

        image = None
        if settings["show-app-icon"]:
            name = client["class"]
            image = Gtk.Image()
            image.set_property("name", "task-box-icon")
            update_image_fallback_desktop(image, name, settings["image-size"], icons_path)
            self.box.pack_start(image, False, False, 4)

        name = client["title"][:settings["name-max-len"]]
        if settings["mark-xwayland"] and client["xwayland"]:
            name = "X|" + name

        if settings["show-app-name"]:
            if not client["workspace"]["name"] == "special" or settings["show-app-name-special"]:
                lbl = Gtk.Label()
                lbl.set_angle(self.settings["angle"])

                lbl.set_text(name)
                self.box.pack_start(lbl, False, False, 6)
        else:
            if name and image:
                image.set_tooltip_text(name)

        if settings["show-layout"]:
            if client["pinned"]:
                img = Gtk.Image()
                update_image(img, "pin", self.settings["image-size"], self.icons_path)
                self.box.pack_start(img, False, False, 0)

            elif client["floating"]:
                img = Gtk.Image()
                update_image(img, "focus-windows", self.settings["image-size"], self.icons_path)
                self.box.pack_start(img, False, False, 0)

    def on_click(self, widget, event, client, popup_at_widget):
        if event.button == 1:
            hyprctl("dispatch focuswindow address:{}".format(self.address))
        if event.button == 3:
            menu = self.context_menu(client)
            menu.show_all()
            if self.position == "bottom":
                menu.popup_at_widget(popup_at_widget, Gdk.Gravity.SOUTH, Gdk.Gravity.NORTH, None)
            else:
                menu.popup_at_widget(popup_at_widget, Gdk.Gravity.NORTH, Gdk.Gravity.SOUTH, None)

    def on_special(self, widget, event):
        hyprctl('dispatch togglespecialworkspace ')

    def sorted_workspace_ids(self):
        """Returns workspace ids, which are first sorted by monitors and then sorted by ids. 
        """
        workspaces = h_list_workspaces()
        monitors = h_list_monitors()
        mon_names = [mon["name"] for mon in monitors]
        ws_ids_by_mon = {mon : [] for mon in mon_names}
        # add workspace ids from rules
        for ws in self.workspace_rules:
            if ws["monitor"] in mon_names:
                ws_ids_by_mon[ws["monitor"]].append(int(ws["workspaceString"]))
            elif ws["monitor"][:5] == "desc:": # check to see if monitor description is used
                for mon in monitors:
                    if mon["description"] == ws["monitor"][5:]:
                        ws_ids_by_mon[mon["name"]].append(int(ws["workspaceString"]))
        # add workspace ids from workspaces
        for ws in workspaces:
            if ws["id"] not in ws_ids_by_mon[ws["monitor"]]:
                ws_ids_by_mon[ws["monitor"]].append(ws["id"])
        # sort the workspaces by id// as is done by default in Hyprland
        for mon in ws_ids_by_mon:
            ws_ids_by_mon[mon].sort()
        return sum([ws_ids_by_mon[mon] for mon in ws_ids_by_mon], [])


    def context_menu(self, client):
        menu = Gtk.Menu()
        menu.set_reserve_toggle_size(False)
        workspace_ids = self.workspace_ids_for_context_menu

        # Move to workspace
        for ws_id in workspace_ids:
            hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 3)
            hbox.set_property("halign", Gtk.Align.START)
            img = Gtk.Image()
            update_image(img, "go-next", 16, self.icons_path)
            hbox.pack_start(img, True, True, 0)
            lbl = Gtk.Label.new(str(ws_id))
            hbox.pack_start(lbl, False, False, 0)
            item = Gtk.MenuItem()
            item.add(hbox)
            item.connect("activate", self.movetoworkspace, ws_id)
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
        update_image(img, "window-close", 16, self.icons_path)
        hbox.pack_start(img, True, True, 0)
        item = Gtk.MenuItem()
        item.add(hbox)
        item.connect("activate", self.close, self.address)
        item.set_tooltip_text("closewindow")
        menu.append(item)

        return menu

    def close(self, *args):
        hyprctl("dispatch closewindow address:{}".format(self.address))

    def toggle_floating(self, *args):
        hyprctl("dispatch togglefloating address:{}".format(self.address))

    def fullscreen(self, *args):
        hyprctl("dispatch fullscreen address:{}".format(self.address))

    def pin(self, *args):
        hyprctl("dispatch pin address:{}".format(self.address))
        # The above doesn't trigger any event. We need a workaround:
        hyprctl("dispatch focuswindow title:''")
        hyprctl("dispatch focuswindow address:{}".format(self.address))

    def movetoworkspace(self, menuitem, ws_num):
        hyprctl("dispatch movetoworkspace {},address:{}".format(ws_num, self.address))
