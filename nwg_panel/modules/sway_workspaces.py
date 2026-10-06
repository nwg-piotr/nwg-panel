#!/usr/bin/env python3

from gi.repository import Gtk, Gdk

import nwg_panel.common
from nwg_panel.tools import check_key, get_icon_name, update_image, update_image_fallback_desktop, load_autotiling


class SwayWorkspaces(Gtk.Box):
    def __init__(self, settings, i3, icons_path):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.settings = settings
        self.i3 = i3
        self.num_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.num_box.set_property("name", "sway-workspaces")
        self.ws_num2box = {}
        self.ws_num2lbl = {}
        self.name_label = Gtk.Label()
        self.name_label.set_property("name", "sway-workspaces-name")
        self.win_id = ""
        self.win_pid = None
        self.icon = Gtk.Image()
        self.icon.set_property("name", "sway-workspaces-icon")
        self.layout_icon = Gtk.Image()
        self.icons_path = icons_path
        self.autotiling = load_autotiling()
        tree = self.i3.get_tree()
        workspaces = self.i3.get_workspaces()
        self.build_box(tree, workspaces)
        self.refresh(tree, workspaces)
        # refreshed by main.py from a single, coalesced get_tree() for all sway modules (#395)
        nwg_panel.common.sway_workspaces_list.append(self)

    def build_box(self, tree, workspaces):
        check_key(self.settings, "numbers", [])
        check_key(self.settings, "custom-labels", [])
        check_key(self.settings, "focused-labels", [])
        check_key(self.settings, "show-icon", True)
        check_key(self.settings, "image-size", 16)
        check_key(self.settings, "show-name", True)
        check_key(self.settings, "name-length", 40)
        check_key(self.settings, "mark-autotiling", True)
        check_key(self.settings, "mark-content", True)
        check_key(self.settings, "hide-empty", False)
        check_key(self.settings, "show-layout", True)
        check_key(self.settings, "angle", 0.0)
        if self.settings["angle"] != 0.0:
            self.set_orientation(Gtk.Orientation.VERTICAL)
            self.num_box.set_orientation(Gtk.Orientation.VERTICAL)

        # prevent from #142
        ws_num = -1
        if tree.find_focused():
            ws_num, win_name, win_id, non_empty, win_layout, numbers = self.find_details(tree, workspaces)

        # a single label applies to every workspace; with `numbers: []` (dynamic list, #190) the single label
        # is kept as is and a longer list is indexed by workspace number (workspace N -> Nth label)
        for key in ("custom-labels", "focused-labels"):
            labels = self.settings[key]
            if self.settings["numbers"]:
                if len(labels) == 1:
                    self.settings[key] = labels * len(self.settings["numbers"])
                elif len(labels) != len(self.settings["numbers"]):
                    self.settings[key] = []

        self.pack_start(self.num_box, False, False, 0)

        for num in self.settings["numbers"]:
            eb, lbl = self.build_number(num, self.label_for(num, ws_num))
            self.num_box.pack_start(eb, False, False, 0)

            if num == str(ws_num):
                eb.set_property("name", "task-box-focused")
            else:
                eb.set_property("name", "task-box")

        if self.settings["show-icon"]:
            self.pack_start(self.icon, False, False, 6)

        if self.settings["show-name"]:
            self.pack_start(self.name_label, False, False, 0)

        if self.settings["show-layout"]:
            self.pack_start(self.layout_icon, False, False, 6)

    def build_number(self, num, label):
        eb = Gtk.EventBox()
        eb.connect("enter_notify_event", self.on_enter_notify_event)
        eb.connect("leave_notify_event", self.on_leave_notify_event)
        eb.connect("button-release-event", self.on_click, num)
        eb.add_events(Gdk.EventMask.SCROLL_MASK)
        eb.connect('scroll-event', self.on_scroll)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        box.set_property("name", "sway-workspaces-item")
        if self.settings["angle"] != 0.0:
            box.set_orientation(Gtk.Orientation.VERTICAL)
        eb.add(box)

        if self.settings["mark-autotiling"]:
            try:
                at = int(num) in self.autotiling
            except:
                at = False
            autotiling = "a" if at in self.autotiling else ""
            lbl = Gtk.Label("{}{}".format(autotiling, label))
        else:
            lbl = Gtk.Label("{}".format(label))
        lbl.set_use_markup(True)
        if self.settings["angle"] != 0.0:
            lbl.set_angle(self.settings["angle"])
            self.name_label.set_angle(self.settings["angle"])

        self.ws_num2box[num] = eb
        self.ws_num2lbl[num] = lbl

        box.pack_start(lbl, False, False, 6)

        return eb, lbl

    def label_for(self, num, ws_num):
        """Label of workspace `num` (str) given the focused workspace number."""
        if self.settings["numbers"]:
            idx = self.settings["numbers"].index(num) if num in self.settings["numbers"] else None
        else:
            # dynamic list (#190): workspace N -> Nth label, a named workspace has no index
            try:
                idx = int(num) - 1
            except ValueError:
                idx = None
        for key in (("focused-labels",) if num == str(ws_num) else ()) + ("custom-labels",):
            labels = self.settings[key]
            if labels and idx is not None and 0 <= idx < len(labels):
                return labels[idx]
            # dynamic list: a single label applies to every workspace, named ones included (with `numbers`
            # set, it has already been repeated for each of them)
            if len(labels) == 1 and not self.settings["numbers"]:
                return labels[0]
        return str(num)

    def refresh(self, tree, workspaces):
        # called on the GTK main loop with data fetched once for all sway modules
        if tree.find_focused():
            ws_num, win_name, win_id, non_empty, win_layout, numbers = self.find_details(tree, workspaces)

            if len(self.settings["numbers"]) > 0:
                numbers = self.settings["numbers"]
            else:
                numbers.sort(key=lambda n: (int(n) if n.isdigit() else 1 << 30, n))  # #190: sorted

            if ws_num > 0:
                for num in self.ws_num2lbl:
                    self.ws_num2lbl[num].hide()

                for position, num in enumerate(numbers):
                    try:
                        int_num = int(num)
                    except ValueError:
                        int_num = 0

                    text = self.label_for(num, ws_num)

                    if num not in self.ws_num2lbl:
                        eb, lbl = self.build_number(num, text)
                        self.num_box.pack_start(eb, False, False, 0)
                        eb.show_all()
                    if not self.settings["numbers"]:
                        self.num_box.reorder_child(self.ws_num2box[num], position)  # #190: keep sorted

                    lbl = self.ws_num2lbl[num]

                    if not self.settings["hide-empty"] or int_num in non_empty or num == str(ws_num):
                        lbl.show()
                    else:
                        lbl.hide()

                    # mark non-empty WS with CSS ID
                    if int_num in non_empty:
                        lbl.set_property("name", "workspace-occupied")

                    # mark non-empty WS with a dot
                    if self.settings["mark-content"]:
                        if int_num in non_empty:
                            if not text.endswith("."):
                                text += "."
                        else:
                            if text.endswith("."):
                                text = text[0:-1]

                    lbl.set_markup(text)

                    if num == str(ws_num):
                        self.ws_num2box[num].set_property("name", "task-box-focused")
                    else:
                        self.ws_num2box[num].set_property("name", "task-box")

                if self.settings["show-icon"] and win_id != self.win_id:
                    self.update_icon(win_id, win_name)
                    self.win_id = win_id

            if self.settings["show-name"]:
                self.name_label.set_text(win_name)

            if self.settings["show-layout"]:
                if win_name:
                    if win_layout == "splith":
                        update_image(self.layout_icon, "go-next-symbolic", self.settings["image-size"], self.icons_path)
                    elif win_layout == "splitv":
                        update_image(self.layout_icon, "go-down-symbolic", self.settings["image-size"], self.icons_path)
                    elif win_layout == "tabbed":
                        update_image(self.layout_icon, "view-dual-symbolic", self.settings["image-size"],
                                     self.icons_path)
                    elif win_layout == "stacked":
                        update_image(self.layout_icon, "view-paged-symbolic", self.settings["image-size"],
                                     self.icons_path)
                    else:
                        update_image(self.layout_icon, "window-pop-out-symbolic", self.settings["image-size"],
                                     self.icons_path)

                    if not self.layout_icon.get_visible():
                        self.layout_icon.show()
                else:
                    if self.layout_icon.get_visible():
                        self.layout_icon.hide()

    def update_icon(self, win_id, win_name):
        loaded_icon = False
        if win_id and win_name:
            try:
                update_image_fallback_desktop(self.icon,
                                              win_id,
                                              self.settings["image-size"],
                                              self.icons_path,
                                              fallback=False)
                loaded_icon = True
                if not self.icon.get_visible():
                    self.icon.show()
            except:
                pass

        if not loaded_icon and self.icon.get_visible():
            self.icon.hide()

    def find_details(self, tree, workspaces):
        # no IPC here: `tree` and `workspaces` are fetched once per refresh for all sway modules (#395)
        ws_num = -1
        win_name = ""
        win_id = ""  # app_id if available, else window_class
        layout = None
        numbers = []

        for ws in workspaces:
            numbers.append(str(ws.num))
            if ws.focused:
                ws_num = ws.num

        non_empty = []
        if self.settings["show-name"] or self.settings["show-icon"]:
            f = tree.find_focused()
            if f.type == "con" and f.name and self.shows_workspace(f.parent.workspace()):
                win_name = f.name[:self.settings["name-length"]]

                if f.app_id:
                    win_id = f.app_id
                elif f.window_class:
                    win_id = f.window_class

            for item in tree.descendants():
                if item.type == "workspace":
                    # find non-empty workspaces
                    # if self.settings["mark-content"] or self.settings["hide-empty"]:
                    tasks_num = 0
                    for d in item.descendants():
                        if d.type == "con" and d.name:
                            tasks_num += 1
                    if tasks_num > 0:
                        non_empty.append(item.num)

                    for node in item.floating_nodes:
                        if self.shows_workspace(node.workspace()):
                            if node.focused and node.name:
                                win_name = node.name[:self.settings["name-length"] - 1]

                                if node.app_id:
                                    win_id = node.app_id
                                elif node.window_class:
                                    win_id = node.window_class
                                layout = "floating"

                            non_empty.append(node.workspace().num)

            if not layout:
                layout = f.parent.layout

        return ws_num, win_name, win_id, non_empty, layout, numbers

    def shows_workspace(self, ws):
        # with `numbers: []` every workspace is listed
        return ws is not None and (not self.settings["numbers"] or str(ws.num) in self.settings["numbers"])

    def on_click(self, event_box, event_button, num):
        nwg_panel.common.i3.command("workspace number {}".format(num))

    def on_scroll(self, event_box, event):
        if event.direction == Gdk.ScrollDirection.UP:
            nwg_panel.common.i3.command("workspace prev")
        elif event.direction == Gdk.ScrollDirection.DOWN:
            nwg_panel.common.i3.command("workspace next")

    def on_enter_notify_event(self, widget, event):
        widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
        widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)

    def on_leave_notify_event(self, widget, event):
        widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
        widget.unset_state_flags(Gtk.StateFlags.SELECTED)
