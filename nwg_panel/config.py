#!/usr/bin/python3

import os
import sys
import subprocess
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

from nwg_panel.tools import get_config_dir, load_json, save_json, load_string, list_outputs, check_key, list_configs, local_dir

dir_name = os.path.dirname(__file__)

sway = os.getenv('SWAYSOCK') is not None

config_dir = get_config_dir()
configs = {}
editor = None
selector_window = None
outputs = list_outputs(sway=sway)


def handle_keyboard(window, event):
    if event.type == Gdk.EventType.KEY_RELEASE and event.keyval == Gdk.KEY_Escape:
        window.close()


class PanelSelector(Gtk.Window):
    def __init__(self):
        super(PanelSelector, self).__init__()
        self.connect("key-release-event", handle_keyboard)
        self.connect('destroy', Gtk.main_quit)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        vbox.pack_start(self.hbox, True, True, 20)
        self.add(vbox)
        grid = self.build_grid()
        self.hbox.pack_start(grid, True, True, 20)
        self.show_all()
        
        self.connect("show", self.refresh)
    
    def refresh(self, w):
        for item in self.hbox.get_children():
            item.destroy()
        grid = self.build_grid()
        self.hbox.pack_start(grid, True, True, 20)
        self.show_all()
    
    def build_grid(self, *args):
        global configs
        configs = list_configs(config_dir)

        grid = Gtk.Grid()
        grid.set_column_spacing(20)
        grid.set_row_spacing(4)

        row = 0
        for path in configs:
            label = Gtk.Label()
            label.set_text("File: '{}'".format(path))
            label.set_halign(Gtk.Align.START)
            grid.attach(label, 0, row, 3, 1)
            row += 1

            panels = configs[path]

            label = Gtk.Label()
            label.set_text("Name:")
            label.set_halign(Gtk.Align.START)
            grid.attach(label, 0, row, 1, 1)

            label = Gtk.Label()
            label.set_text("Output:")
            label.set_halign(Gtk.Align.START)
            grid.attach(label, 1, row, 1, 1)

            label = Gtk.Label()
            label.set_text("Position:")
            label.set_halign(Gtk.Align.START)
            grid.attach(label, 2, row, 1, 1)
            row += 1

            panel_idx = 0
            for panel in panels:
                for item in ["name", "output", "position"]:
                    check_key(panel, item, "")

                label = Gtk.Label()
                label.set_text('"{}"'.format(panel["name"]))
                label.set_halign(Gtk.Align.START)
                grid.attach(label, 0, row, 1, 1)

                label = Gtk.Label()
                label.set_text('"{}"'.format(panel["output"]))
                label.set_halign(Gtk.Align.START)
                grid.attach(label, 1, row, 1, 1)

                label = Gtk.Label()
                label.set_text('"{}"'.format(panel["position"]))
                label.set_halign(Gtk.Align.START)
                grid.attach(label, 2, row, 1, 1)

                button = Gtk.Button.new_from_icon_name("document-edit", Gtk.IconSize.BUTTON)
                button.set_label("edit")
                button.connect("clicked", self.on_button_clicked, path, panel_idx)
                grid.attach(button, 3, row, 1, 1)

                row += 1
                panel_idx += 1
        
        return grid

    def on_button_clicked(self, button, file, panel_idx):
        global editor
        editor = EditorWrapper(self, file, panel_idx)
        editor.set_panel()
        editor.edit_panel()


class EditorWrapper(object):
    def __init__(self, parent, file, panel_idx):
        self.file = file
        self.panel_idx = panel_idx
        self.config = {}
        self.panel = {}
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(dir_name, "glade/config_main.glade"))

        self.window = builder.get_object("main-window")
        self.window.set_transient_for(parent)
        self.window.set_keep_above(True)
        self.window.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.window.connect('destroy', self.show_parent, parent)
        self.window.connect("key-release-event", handle_keyboard)
        self.window.connect("show", self.hide_parent, parent)

        self.scrolled_window = builder.get_object("scrolled-window")

        btn = builder.get_object("btn-panel")
        btn.connect("clicked", self.edit_panel)

        btn = builder.get_object("btn-clock")
        btn.connect("clicked", self.edit_clock)

        btn = builder.get_object("btn-playerctl")
        btn.connect("clicked", self.edit_playerctl)

        btn = builder.get_object("btn-sway-taskbar")
        btn.connect("clicked", self.edit_sway_taskbar)

        btn = builder.get_object("btn-sway-workspaces")
        btn.connect("clicked", self.edit_sway_workspaces)
        
        btn = builder.get_object("btn-cancel")
        btn.connect("clicked", self.quit)

        btn = builder.get_object("btn-apply")
        btn.connect("clicked", self.restart_panel)

        btn = builder.get_object("btn-apply-restart")
        btn.connect("clicked", self.restart_panel, True)

        self.eb_name = None
        self.cb_output = None
        self.cb_position = None
        self.cb_controls = None
        self.cb_layer = None
        self.sb_width = None
        self.ckb_width_auto = None
        self.sb_height = None
        self.sb_margin_top = None
        self.sb_margin_bottom = None
        self.sb_padding_horizontal = None
        self.sb_padding_vertical = None
        self.sb_spacing = None
        self.cb_icons = None
        self.eb_css_name = None

        self.edited = None

        self.set_panel()
        self.edit_panel()
    
        self.window.show_all()
        
    def quit(self, btn):
        selector_window.show_all()
        self.window.close()
    
    def set_panel(self):
        if self.file:
            self.config = load_json(self.file)
            self.panel = self.config[self.panel_idx]
        else:
            self.panel = {}
        defaults = {
            "name": "",
            "output": "",
            "layer": "",
            "position": "",
            "controls": False,
            "width": "auto",
            "height": 0,
            "margin-top": 0,
            "margin-bottom": 0,
            "padding-horizontal": 0,
            "padding-vertical": 0,
            "spacing": 0,
            "icons": "",
            "css-name": ""
        }
        for key in defaults:
            check_key(self.panel, key, defaults[key])

        check_key(self.panel, "controls-settings", {
            "components": [
                "net",
                "brightness",
                "volume",
                "battery"
            ]
        })
    
    def edit_panel(self, *args):
        self.edited = "panel"
        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_panel.glade"))
        grid = builder.get_object("grid")

        self.eb_name = builder.get_object("name")
        self.eb_name.set_text(self.panel["name"])

        self.cb_output = builder.get_object("output")
        for key in outputs:
            self.cb_output.append(key, key)
        if self.panel["output"] and self.panel["output"] in outputs:
            self.cb_output.set_active_id(self.panel["output"])
            
        screen_width, screen_height = None, None
        if self.cb_output.get_active_id() and self.cb_output.get_active_id() in outputs:
            screen_width = outputs[self.cb_output.get_active_id()]["width"]
            screen_height = outputs[self.cb_output.get_active_id()]["height"]

        self.cb_position = builder.get_object("position")
        self.cb_position.set_active_id(self.panel["position"])

        self.cb_controls = builder.get_object("controls")
        if not self.panel["controls"]:
            self.cb_controls.set_active_id("off")
        else:
            if self.panel["controls"] == "right":
                self.cb_controls.set_active_id("right")
            elif self.panel["controls"] == "left":
                self.cb_controls.set_active_id("left")
            else:
                self.cb_controls.set_active_id("off")

        self.cb_layer = builder.get_object("layer")
        self.cb_layer.set_active_id(self.panel["layer"])

        self.sb_width = builder.get_object("width")
        self.sb_width.set_numeric(True)
        upper = float(screen_width + 1) if screen_width is not None else 8193
        adj = Gtk.Adjustment(value=0, lower=0, upper=upper, step_increment=1, page_increment=10, page_size=1)
        self.sb_width.configure(adj, 1, 0)
        
        self.ckb_width_auto = builder.get_object("width-auto")
        if isinstance(self.panel["width"], int):
            self.sb_width.set_value(float(self.panel["width"]))
        else:
            self.ckb_width_auto.set_active(True)
            self.sb_width.set_sensitive(False)
        self.ckb_width_auto.connect("toggled", self.on_auto_toggle, self.sb_width, self.cb_output)

        self.sb_height = builder.get_object("height")
        self.sb_height.set_numeric(True)
        upper = float(screen_height + 1) if screen_height is not None else 4602
        adj = Gtk.Adjustment(value=0, lower=0, upper=upper, step_increment=1, page_increment=10, page_size=1)
        self.sb_height.configure(adj, 1, 0)
        self.sb_height.set_value(float(self.panel["height"]))

        self.sb_margin_top = builder.get_object("margin-top")
        self.sb_margin_top.set_numeric(True)
        upper = float(screen_height + 1) if screen_height is not None else 4602
        if self.sb_height.get_value():
            upper = upper - self.sb_height.get_value()
        adj = Gtk.Adjustment(value=0, lower=0, upper=upper, step_increment=1, page_increment=10, page_size=1)
        self.sb_margin_top.configure(adj, 1, 0)
        self.sb_margin_top.set_value(float(self.panel["margin-top"]))

        self.sb_margin_bottom = builder.get_object("margin-bottom")
        self.sb_margin_bottom.set_numeric(True)
        upper = float(screen_height + 1) if screen_height is not None else 4602
        if self.sb_height.get_value():
            upper = upper - self.sb_height.get_value()
        adj = Gtk.Adjustment(value=0, lower=0, upper=upper, step_increment=1, page_increment=10, page_size=1)
        self.sb_margin_bottom.configure(adj, 1, 0)
        self.sb_margin_bottom.set_value(float(self.panel["margin-bottom"]))

        self.sb_padding_horizontal = builder.get_object("padding-horizontal")
        self.sb_padding_horizontal.set_numeric(True)
        upper = float(screen_width / 3 + 1) if screen_width is not None else 640
        adj = Gtk.Adjustment(value=0, lower=0, upper=upper, step_increment=1, page_increment=10, page_size=1)
        self.sb_padding_horizontal.configure(adj, 1, 0)
        self.sb_padding_horizontal.set_value(float(self.panel["padding-horizontal"]))

        self.sb_padding_vertical = builder.get_object("padding-vertical")
        self.sb_padding_vertical.set_numeric(True)
        upper = float(screen_height / 3 + 1) if screen_height is not None else 360
        adj = Gtk.Adjustment(value=0, lower=0, upper=upper, step_increment=1, page_increment=10, page_size=1)
        self.sb_padding_vertical.configure(adj, 1, 0)
        self.sb_padding_vertical.set_value(float(self.panel["padding-vertical"]))

        self.sb_spacing = builder.get_object("spacing")
        self.sb_spacing.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=0, upper=201, step_increment=1, page_increment=10, page_size=1)
        self.sb_spacing.configure(adj, 1, 0)
        self.sb_spacing.set_value(float(self.panel["spacing"]))

        self.cb_icons = builder.get_object("icons")
        if self.panel["icons"]:
            self.cb_icons.set_active_id(self.panel["icons"])
        else:
            self.cb_icons.set_active_id("gtk")

        self.eb_css_name = builder.get_object("css-name")
        self.eb_css_name.set_text(self.panel["css-name"])

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(grid)
        
    def on_auto_toggle(self, checkbutton, sb_width, cb_output):
        if not checkbutton.get_active():
            o_name = cb_output.get_active_id()
            sb_width.set_sensitive(True)
            if o_name in outputs:
                sb_width.set_value(float(outputs[o_name]["width"]))
        else:
            sb_width.set_sensitive(False)

    def update_panel(self):
        val = self.eb_name.get_text()
        if val:
            self.panel["name"] = val

        val = self.cb_output.get_active_id()
        if val:
            self.panel["output"] = val

        val = self.cb_position.get_active_id()
        if val:
            self.panel["position"] = val

        val = self.cb_controls.get_active_id()
        if val:
            if val in ["left", "right"]:
                self.panel["controls"] = val
            else:
                self.panel["controls"] = "off"

        val = self.cb_layer.get_active_id()
        if val:
            self.panel["layer"] = val

        val = self.ckb_width_auto.get_active()
        if val:
            self.panel["width"] = "auto"
        else:
            val = self.sb_width.get_value()
            if val is not None:
                self.panel["width"] = int(val)

        val = self.sb_height.get_value()
        if val is not None:
            self.panel["height"] = int(val)

        val = self.sb_margin_top.get_value()
        if val is not None:
            self.panel["margin-top"] = int(val)

        val = self.sb_margin_bottom.get_value()
        if val is not None:
            self.panel["margin-bottom"] = int(val)

        val = self.sb_padding_horizontal.get_value()
        if val is not None:
            self.panel["padding-horizontal"] = int(val)

        val = self.sb_padding_vertical.get_value()
        if val is not None:
            self.panel["padding-vertical"] = int(val)

        val = self.sb_spacing.get_value()
        if val is not None:
            self.panel["spacing"] = int(val)

        val = self.cb_icons.get_active_id()
        if val != "gtk":
            self.panel["icons"] = val
        else:
            self.panel["icons"] = ""

        val = self.eb_css_name.get_text()
        if val:
            self.panel["css-name"] = val

        save_json(self.config, self.file)

    def hide_parent(self, w, parent):
        parent.hide()

    def show_parent(self, w, parent):
        parent.show()

    def restart_panel(self, w, restart=False):
        if self.edited == "panel":
            self.update_panel()
        elif self.edited == "sway-taskbar":
            self.update_sway_taskbar()
        elif self.edited == "clock":
            self.update_clock()
        elif self.edited == "playerctl":
            self.update_playerctl()
        elif self.edited == "sway-workspaces":
            self.update_sway_workspaces()

        cmd = "nwg-panel"
        try:
            args_string = load_string(os.path.join(local_dir(), "args"))
            cmd = "nwg-panel {}".format(args_string)
        except:
            pass
        if restart:
            print("Restarting panels".format(cmd))
            subprocess.Popen('exec {}'.format(cmd), shell=True)
        self.window.close()

    def edit_sway_taskbar(self, *args):
        self.edited = "sway-taskbar"
        check_key(self.panel, "sway-taskbar", {})
        settings = self.panel["sway-taskbar"]
        defaults = {
            "workspace-menu": [1, 2, 3, 4, 5, 6, 7, 8],
            "name-max-len": 20,
            "image-size": 16,
            "workspaces-spacing": 0,
            "task-padding": 0,
            "show-app-icon": True,
            "show-app-name": True,
            "show-layout": True,
            "workspace-buttons": True,
            "all-outputs": False
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_sway_taskbar.glade"))
        grid = builder.get_object("grid")

        self.eb_workspace_menu = builder.get_object("workspace-menu")
        workspaces = settings["workspace-menu"]
        text = ""
        for item in workspaces:
            text += str(item) + " "
        self.eb_workspace_menu.set_text(text.strip())
        self.eb_workspace_menu.connect("changed", self.validate_workspaces)

        self.sb_name_max_len = builder.get_object("name-max-len")
        self.sb_name_max_len.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=1, upper=257, step_increment=1, page_increment=10, page_size=1)
        self.sb_name_max_len.configure(adj, 1, 0)
        self.sb_name_max_len.set_value(settings["name-max-len"])

        self.sb_image_size = builder.get_object("image-size")
        self.sb_image_size.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=8, upper=129, step_increment=1, page_increment=10, page_size=1)
        self.sb_image_size.configure(adj, 1, 0)
        self.sb_image_size.set_value(settings["image-size"])

        self.sb_workspace_spacing = builder.get_object("workspaces-spacing")
        self.sb_workspace_spacing.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=0, upper=1000, step_increment=1, page_increment=10, page_size=1)
        self.sb_workspace_spacing.configure(adj, 1, 0)
        self.sb_workspace_spacing.set_value(settings["workspaces-spacing"])

        self.sb_task_padding = builder.get_object("task-padding")
        self.sb_task_padding.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=0, upper=257, step_increment=1, page_increment=10, page_size=1)
        self.sb_task_padding.configure(adj, 1, 0)
        self.sb_task_padding.set_value(settings["task-padding"])

        self.ckb_show_app_icon = builder.get_object("show-app-icon")
        self.ckb_show_app_icon.set_active(settings["show-app-icon"])

        self.ckb_show_app_name = builder.get_object("show-app-name")
        self.ckb_show_app_name.set_active(settings["show-app-name"])

        self.ckb_show_layout = builder.get_object("show-layout")
        self.ckb_show_layout.set_active(settings["show-layout"])

        self.workspace_buttons = builder.get_object("workspace-buttons")
        self.workspace_buttons.set_active(settings["workspace-buttons"])

        self.ckb_all_outputs = builder.get_object("all-outputs")
        self.ckb_all_outputs.set_active(settings["all-outputs"])

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(grid)
        
    def validate_workspaces(self, gtk_entry):
        valid_text = ""
        for char in gtk_entry.get_text():
            if char.isdigit() or char == " ":
                valid_text += char
        while '  ' in valid_text:
            valid_text = valid_text.replace('  ', ' ')
        gtk_entry.set_text(valid_text)
        
    def update_sway_taskbar(self):
        settings = self.panel["sway-taskbar"]

        val = self.eb_workspace_menu.get_text()
        if val:
            settings["workspace-menu"] = val.split()

        val = self.sb_name_max_len.get_value()
        if val is not None:
            settings["name-max-len"] = int(val)

        val = self.sb_image_size.get_value()
        if val is not None:
            settings["image-size"] = int(val)

        val = self.sb_workspace_spacing.get_value()
        if val is not None:
            settings["workspaces-spacing"] = int(val)

        val = self.sb_task_padding.get_value()
        if val is not None:
            settings["task-padding"] = int(val)
            
        val = self.ckb_show_app_icon.get_active()
        if val is not None:
            settings["show-app-icon"] = val

        val = self.ckb_show_app_name.get_active()
        if val is not None:
            settings["show-app-name"] = val

        val = self.ckb_show_layout.get_active()
        if val is not None:
            settings["show-layout"] = val

        val = self.workspace_buttons.get_active()
        if val is not None:
            settings["workspace-buttons"] = val

        val = self.ckb_all_outputs.get_active()
        if val is not None:
            settings["all-outputs"] = val

        save_json(self.config, self.file)
        
    def edit_clock(self, *args):
        self.edited = "clock"
        check_key(self.panel, "clock", {})
        settings = self.panel["clock"]
        defaults = {
            "format": "%a, %d. %b  %H:%M:%S",
            "tooltip-text": "",
            "on-left-click": "",
            "on-middle-click": "",
            "on-right-click": "",
            "on-scroll-up": "",
            "on-scroll-down": "",
            "css-name": "clock",
            "interval": 1
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_clock.glade"))
        grid = builder.get_object("grid")

        self.eb_format = builder.get_object("format")
        self.eb_format.set_text(settings["format"])

        self.eb_tooltip_text = builder.get_object("tooltip-text")
        self.eb_tooltip_text.set_text(settings["tooltip-text"])

        self.eb_on_left_click = builder.get_object("on-left-click")
        self.eb_on_left_click.set_text(settings["on-left-click"])

        self.eb_on_middle_click = builder.get_object("on-middle-click")
        self.eb_on_middle_click.set_text(settings["on-middle-click"])

        self.eb_on_right_click = builder.get_object("on-right-click")
        self.eb_on_right_click.set_text(settings["on-right-click"])

        self.eb_on_scroll_up = builder.get_object("on-scroll-up")
        self.eb_on_scroll_up.set_text(settings["on-scroll-up"])

        self.eb_on_scroll_down = builder.get_object("on-scroll-down")
        self.eb_on_scroll_down.set_text(settings["on-scroll-down"])

        self.eb_css_name_clock = builder.get_object("css-name")
        self.eb_css_name_clock.set_text(settings["css-name"])

        self.sb_interval = builder.get_object("interval")
        self.sb_interval.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=1, upper=3600, step_increment=1, page_increment=10, page_size=1)
        self.sb_interval.configure(adj, 1, 0)
        self.sb_interval.set_value(settings["interval"])

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(grid)

    def update_clock(self):
        settings = self.panel["clock"]

        settings["format"] = self.eb_format.get_text()
        settings["tooltip-text"] = self.eb_tooltip_text.get_text()
        settings["on-left-click"] = self.eb_on_left_click.get_text()
        settings["on-middle-click"] = self.eb_on_middle_click.get_text()
        settings["on-right-click"] = self.eb_on_right_click.get_text()

        settings["on-scroll-up"] = self.eb_on_scroll_up.get_text()
        settings["on-scroll-down"] = self.eb_on_scroll_down.get_text()
        settings["css-name"] = self.eb_css_name_clock.get_text()

        val = self.sb_interval.get_value()
        if val is not None:
            settings["interval"] = int(val)

        save_json(self.config, self.file)

    def edit_playerctl(self, *args):
        self.edited = "playerctl"
        check_key(self.panel, "playerctl", {})
        settings = self.panel["playerctl"]
        defaults = {
            "buttons-position": "left",
            "icon-size": 16,
            "chars": 30,
            "button-css-name": "",
            "label-css-name": "",
            "interval": 1
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_playerctl.glade"))
        grid = builder.get_object("grid")

        self.cb_buttons_position = builder.get_object("buttons-position")
        self.cb_buttons_position.set_active_id(settings["buttons-position"])
        
        self.sc_icon_size_playerctl = builder.get_object("icon-size")
        self.sc_icon_size_playerctl.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=8, upper=128, step_increment=1, page_increment=10, page_size=1)
        self.sc_icon_size_playerctl.configure(adj, 1, 0)
        self.sc_icon_size_playerctl.set_value(settings["icon-size"])

        self.sc_chars = builder.get_object("chars")
        self.sc_chars.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=1, upper=256, step_increment=1, page_increment=10, page_size=1)
        self.sc_chars.configure(adj, 1, 0)
        self.sc_chars.set_value(settings["chars"])

        self.sc_interval_playerctl = builder.get_object("interval")
        self.sc_interval_playerctl.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=0, upper=60, step_increment=1, page_increment=10, page_size=1)
        self.sc_interval_playerctl.configure(adj, 1, 0)
        self.sc_interval_playerctl.set_value(settings["interval"])
        
        self.eb_button_css_name = builder.get_object("button-css-name")
        self.eb_button_css_name.set_text(settings["button-css-name"])

        self.eb_label_css_name = builder.get_object("label-css-name")
        self.eb_label_css_name.set_text(settings["label-css-name"])

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(grid)

    def update_playerctl(self):
        settings = self.panel["playerctl"]

        val = self.cb_buttons_position.get_active_id()
        if val:
            settings["buttons-position"] = val

        settings["icon-size"] = int(self.sc_icon_size_playerctl.get_value())
        settings["chars"] = int(self.sc_chars.get_value())

        settings["button-css-name"] = self.eb_button_css_name.get_text()
        settings["label-css-name"] = self.eb_label_css_name.get_text()

        settings["interval"] = int(self.sc_interval_playerctl.get_value())

        save_json(self.config, self.file)
        
    def edit_sway_workspaces(self, *args):
        self.edited = "sway-workspaces"
        check_key(self.panel, "sway-workspaces", {})
        settings = self.panel["sway-workspaces"]
        defaults = {
            "numbers": [1, 2, 3, 4, 5, 6, 7, 8]
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_sway_workspaces.glade"))
        grid = builder.get_object("grid")

        self.eb_workspaces_menu = builder.get_object("numbers")
        workspaces = settings["numbers"]
        text = ""
        for item in workspaces:
            text += str(item) + " "
        self.eb_workspaces_menu.set_text(text.strip())
        self.eb_workspaces_menu.connect("changed", self.validate_workspaces)

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(grid)

    def update_sway_workspaces(self):
        settings = self.panel["sway-workspaces"]

        val = self.eb_workspaces_menu.get_text()
        if val:
            settings["numbers"] = val.split()

        save_json(self.config, self.file)


def main():
    global configs
    configs = list_configs(config_dir)

    GLib.set_prgname('nwg-panel')

    global selector_window
    selector_window = PanelSelector()

    Gtk.main()


if __name__ == "__main__":
    sys.exit(main())
