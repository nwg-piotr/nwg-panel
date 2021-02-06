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
        self.window.connect('destroy', self.release_parent, parent)
        self.window.connect("key-release-event", handle_keyboard)
        self.window.connect("show", self.lock_parent, parent)

        self.scrolled_window = builder.get_object("scrolled-window")

        btn_cancel = builder.get_object("btn-cancel")
        btn_cancel.connect("clicked", self.quit)

        btn_apply = builder.get_object("btn-apply")
        btn_apply.connect("clicked", self.restart_panel)

        btn_apply = builder.get_object("btn-apply-restart")
        btn_apply.connect("clicked", self.restart_panel, True)

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
        self.sb_items_padding = None
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
            "items-padding": 0,
            "icons": "",
            "css-name": ""
        }
        for key in defaults:
            check_key(self.panel, key, defaults[key])

        check_key(self.panel, "controls-settings", {
            "alignment": "right",
            "components": [
                "net",
                "brightness",
                "volume",
                "battery"
            ]
        })
    
    def edit_panel(self):
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
            if self.panel["controls-settings"]["alignment"] == "right":
                self.cb_controls.set_active_id("right")
            elif self.panel["controls-settings"]["alignment"] == "left":
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

        self.sb_items_padding = builder.get_object("items-padding")
        self.sb_items_padding.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=0, upper=201, step_increment=1, page_increment=10, page_size=1)
        self.sb_items_padding.configure(adj, 1, 0)
        self.sb_items_padding.set_value(float(self.panel["items-padding"]))

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
            self.panel["controls"] = val

        print(self.cb_controls.get_active_id())
        print(self.cb_layer.get_active_id())
        print(self.sb_width.get_value())
        print(self.ckb_width_auto.get_active())
        print(self.sb_height.get_value())
        print(self.sb_margin_top.get_value())
        print(self.sb_margin_bottom.get_value())
        print(self.sb_padding_horizontal.get_value())
        print(self.sb_padding_vertical.get_value())
        print(self.sb_spacing.get_value())
        print(self.sb_items_padding.get_value())
        print(self.cb_icons.get_active_id())
        print(self.eb_css_name.get_text())

        save_json(self.config, self.file)

    def lock_parent(self, w, parent):
        parent.hide()

    def release_parent(self, w, parent):
        parent.show()

    def restart_panel(self, w, restart=False):
        if self.edited == "panel":
            self.update_panel()

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


def main():
    global configs
    configs = list_configs(config_dir)

    GLib.set_prgname('nwg-panel-config')

    global selector_window
    selector_window = PanelSelector()

    Gtk.main()


if __name__ == "__main__":
    sys.exit(main())
