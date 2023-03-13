#!/usr/bin/env python3

from gi.repository import Gtk, GdkPixbuf, Gdk

import nwg_panel.common
from nwg_panel.tools import check_key, get_icon_name, update_image, load_autotiling


class SwayWorkspaces(Gtk.Box):
    def __init__(self, settings, i3, icons_path, output):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.settings = settings
        self.i3 = i3
        self.panel_output = output
        self.num_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.ws_num2box = {}
        self.ws_num2lbl = {}
        self.name_label = Gtk.Label()
        self.win_id = ""
        self.win_pid = None
        self.icon = Gtk.Image()
        self.layout_icon = Gtk.Image()
        self.icons_path = icons_path
        self.autotiling = load_autotiling()
        self.build_box()

    def build_box(self):
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
        check_key(self.settings, "hide-other-outputs", False)
        check_key(self.settings, "show-layout", True)
        check_key(self.settings, "angle", 0.0)
        if self.settings["angle"] != 0.0:
            self.set_orientation(Gtk.Orientation.VERTICAL)

        # prevent from #142
        ws_num = -1
        if self.i3.get_tree().find_focused():
            ws_num, win_name, win_id, non_empty, win_layout, numbers, ws_defs = self.find_details()

        self.pack_start(self.num_box, False, False, 0)

        for idx, num in enumerate(self.settings["numbers"]):
            try:
                int_num = int(num)
            except:
                int_num = 0

            label = self.get_ws_label(int_num, focused = (str(num) == str(ws_num)))

            eb, lbl = self.build_number(num, label)
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
        if self.settings["angle"] != 0.0:
            lbl.set_angle(self.settings["angle"])
            self.name_label.set_angle(self.settings["angle"])

        self.ws_num2box[num] = eb
        self.ws_num2lbl[num] = lbl

        box.pack_start(lbl, False, False, 6)

        return eb, lbl

    def get_ws_label(self, num, idx = None, ws_defs = None, focused = False):
        """
        Get the text to display for a workspace:
        - num: the number of the workspace (as integer)
        - idx: the index of the workspace in ws_defs (if defined)
        - focused: if the workspace is currently focused
        - ws_defs: as returned by find_details()
        """

        # config_idx is the index of the current workspace in the
        # configuration. It is the index of the workspace in the
        # numbers config field, or the an index based on the
        # workspace number, first workspace being number 1
        config_idx = None
        if num in self.settings["numbers"]:
            config_idx = self.settings["numbers"].index(num)
        elif len(self.settings["numbers"]) == 0:
            config_idx = num - 1

        if focused:
            labels = self.settings["focused-labels"]
        else:
            labels = self.settings["custom-labels"]

        if labels and config_idx in range(len(labels)):
            text = labels[config_idx]
        elif labels and len(labels) == 1:
            text = labels[0]
        elif idx in range(len(ws_defs)):
            text = ws_defs[idx]['name']
        else:
            text = str(num)

        return text

    def refresh(self):
        if self.i3.get_tree().find_focused():
            ws_num, win_name, win_id, non_empty, win_layout, numbers, ws_defs = self.find_details()

            custom_labels = self.settings["custom-labels"]
            focused_labels = self.settings["focused-labels"]

            if len(self.settings["numbers"]) > 0:
                numbers = self.settings["numbers"]

            if ws_num > 0:
                for num in self.ws_num2lbl:
                    self.ws_num2lbl[num].hide()

                for idx, num in enumerate(numbers):
                    focused = (str(num) == str(ws_num))
                    try:
                        int_num = int(num)
                    except:
                        int_num = 0

                    text = self.get_ws_label(int_num, idx, ws_defs,
                                             focused = focused)

                    if num not in self.ws_num2lbl:
                        eb, lbl = self.build_number(num, text)
                        self.num_box.pack_start(eb, False, False, 0)
                        eb.show_all()

                    lbl = self.ws_num2lbl[num]

                    if not self.settings["hide-empty"] or int_num in non_empty or focused:
                        lbl.show()
                    else:
                        lbl.hide()

                    # mark non-empty WS with a dot
                    if self.settings["mark-content"]:
                        if int_num in non_empty:
                            if not text.endswith("."):
                                text += "."
                        else:
                            if text.endswith("."):
                                text = text[0:-1]

                    lbl.set_text(text)

                    if focused:
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
        if win_id and win_name:
            icon_from_desktop = get_icon_name(win_id)
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
        win_id = ""  # app_id if available, else window_class
        layout = None
        numbers = []
        ws_defs = []

        for ws in workspaces:
            _, _, name = ws.name.partition(':')
            if len(name) == 0:
                name = str(ws.num)

            hide_other_outputs = self.settings["hide-other-outputs"] and self.panel_output is not None
            if hide_other_outputs and ws.output != self.panel_output:
                continue

            ws_defs.append({
                'num': int(ws.num),
                'name': name
            })
            if ws.focused:
                ws_num = ws.num

        # Sort ws_defs before constructing numbers and names to ensure
        # dynamic workspaces always appear in sorted order
        ws_defs.sort(key = lambda ws: ws['num'])
        for _idx, ws in enumerate(ws_defs):
            numbers.append(ws['num'])

        non_empty = []
        if self.settings["show-name"] or self.settings["show-icon"]:
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
                    if self.settings["mark-content"] or self.settings["hide-empty"]:
                        tasks_num = 0
                        for d in item.descendants():
                            if d.type == "con" and d.name:
                                tasks_num += 1
                        if tasks_num > 0:
                            non_empty.append(item.num)

                    for node in item.floating_nodes:
                        if str(node.workspace().num) in self.settings["numbers"]:
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

        return ws_num, win_name, win_id, non_empty, layout, numbers, ws_defs

    def on_click(self, event_box, event_button, num):
        nwg_panel.common.i3.command("workspace number {}".format(num))

    def on_scroll(self, event_box, event):
        hide_other_outputs = self.settings["hide-other-outputs"] and self.panel_output is not None
        if event.direction == Gdk.ScrollDirection.UP:
            if hide_other_outputs:
                nwg_panel.common.i3.command("workspace prev_on_output")
            else:
                nwg_panel.common.i3.command("workspace prev")
        elif event.direction == Gdk.ScrollDirection.DOWN:
            if hide_other_outputs:
                nwg_panel.common.i3.command("workspace next_on_output")
            else:
                nwg_panel.common.i3.command("workspace next")

    def on_enter_notify_event(self, widget, event):
        widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
        widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)

    def on_leave_notify_event(self, widget, event):
        widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
        widget.unset_state_flags(Gtk.StateFlags.SELECTED)
