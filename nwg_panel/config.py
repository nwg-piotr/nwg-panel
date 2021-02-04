#!/usr/bin/python3

import sys
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

from nwg_panel.tools import get_config_dir, load_json, list_outputs, check_key, is_command, list_configs

config_dir = get_config_dir()
configs = {}
editor = None
selector_window = None
outputs = list_outputs()


def handle_keyboard(window, event):
    if event.type == Gdk.EventType.KEY_RELEASE and event.keyval == Gdk.KEY_Escape:
        window.close()


class PanelSelector(Gtk.Window):
    def __init__(self):
        super(PanelSelector, self).__init__()
        self.connect("key-release-event", handle_keyboard)
        self.connect('destroy', Gtk.main_quit)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        vbox.pack_start(hbox, True, True, 20)

        self.add(vbox)

        grid = Gtk.Grid()
        grid.set_column_spacing(20)
        grid.set_row_spacing(4)

        hbox.pack_start(grid, True, True, 20)

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

        self.show_all()
    
    def on_button_clicked(self, button, file, panel_idx):
        global editor
        editor = EditorWrapper(self)
        editor.set_panel(file, panel_idx)
        editor.edit_panel()


class EditorWrapper(object):
    def __init__(self, parent):
        self.file = ""
        self.config = {}
        self.panel = {}
        builder = Gtk.Builder()
        builder.add_from_file("glade/config_main.glade")

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
        
        self.set_panel()
        self.edit_panel()
    
        self.window.show_all()
        
    def quit(self, btn):
        selector_window.show_all()
        self.window.close()
    
    def set_panel(self, file="", panel_num=0):
        self.file = file
        if file:
            self.config = load_json(file)
            self.panel = self.config[panel_num]
        else:
            self.panel = {}
        defaults = {
            "name": "",
            "output": "",
            "layer": "",
            "position": "",
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
    
    def edit_panel(self):
        builder = Gtk.Builder.new_from_file("glade/config_panel.glade")
        grid = builder.get_object("grid")

        eb_name = builder.get_object("name")
        eb_name.set_text(self.panel["name"])

        cb_output = builder.get_object("output")
        for key in outputs:
            cb_output.append(key, key)
        if self.panel["output"] and self.panel["output"] in outputs:
            cb_output.set_active_id(self.panel["output"])
            
        screen_width, screen_height = None, None
        if cb_output.get_active_id() and cb_output.get_active_id() in outputs:
            screen_width = outputs[cb_output.get_active_id()]["width"]
            screen_height = outputs[cb_output.get_active_id()]["height"]

        cb_position = builder.get_object("position")
        cb_position.set_active_id(self.panel["position"])

        cb_layer = builder.get_object("layer")
        cb_layer.set_active_id(self.panel["layer"])

        sb_width = builder.get_object("width")
        sb_width.set_numeric(True)
        upper = float(screen_width + 1) if screen_width is not None else 8193
        adj = Gtk.Adjustment(value=0, lower=0, upper=upper, step_increment=1, page_increment=10, page_size=1)
        sb_width.configure(adj, 1, 0)
        
        ckb_width_auto = builder.get_object("width-auto")
        if isinstance(self.panel["width"], int):
            sb_width.set_value(float(self.panel["width"]))
        else:
            ckb_width_auto.set_active(True)
            sb_width.set_sensitive(False)
        ckb_width_auto.connect("toggled", self.on_auto_toggle, sb_width, cb_output)

        sb_height = builder.get_object("height")
        sb_height.set_numeric(True)
        upper = float(screen_height + 1) if screen_height is not None else 4602
        adj = Gtk.Adjustment(value=0, lower=0, upper=upper, step_increment=1, page_increment=10, page_size=1)
        sb_height.configure(adj, 1, 0)
        sb_height.set_value(float(self.panel["height"]))

        sb_margin_top = builder.get_object("margin-top")
        sb_margin_top.set_numeric(True)
        upper = float(screen_height + 1) if screen_height is not None else 4602
        if sb_height.get_value():
            upper = upper - sb_height.get_value()
        adj = Gtk.Adjustment(value=0, lower=0, upper=upper, step_increment=1, page_increment=10, page_size=1)
        sb_margin_top.configure(adj, 1, 0)
        sb_margin_top.set_value(float(self.panel["margin-top"]))

        sb_margin_bottom = builder.get_object("margin-bottom")
        sb_margin_bottom.set_numeric(True)
        upper = float(screen_height + 1) if screen_height is not None else 4602
        if sb_height.get_value():
            upper = upper - sb_height.get_value()
        adj = Gtk.Adjustment(value=0, lower=0, upper=upper, step_increment=1, page_increment=10, page_size=1)
        sb_margin_bottom.configure(adj, 1, 0)
        sb_margin_bottom.set_value(float(self.panel["margin-bottom"]))

        sb_padding_horizontal = builder.get_object("padding-horizontal")
        sb_padding_horizontal.set_numeric(True)
        upper = float(screen_width / 3 + 1) if screen_width is not None else 640
        adj = Gtk.Adjustment(value=0, lower=0, upper=upper, step_increment=1, page_increment=10, page_size=1)
        sb_padding_horizontal.configure(adj, 1, 0)
        sb_padding_horizontal.set_value(float(self.panel["padding-horizontal"]))

        sb_padding_vertical = builder.get_object("padding-vertical")
        sb_padding_vertical.set_numeric(True)
        upper = float(screen_height / 3 + 1) if screen_height is not None else 360
        adj = Gtk.Adjustment(value=0, lower=0, upper=upper, step_increment=1, page_increment=10, page_size=1)
        sb_padding_vertical.configure(adj, 1, 0)
        sb_padding_vertical.set_value(float(self.panel["padding-vertical"]))

        sb_spacing = builder.get_object("spacing")
        sb_spacing.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=0, upper=201, step_increment=1, page_increment=10, page_size=1)
        sb_spacing.configure(adj, 1, 0)
        sb_spacing.set_value(float(self.panel["spacing"]))

        sb_items_padding = builder.get_object("items-padding")
        sb_items_padding.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=0, upper=201, step_increment=1, page_increment=10, page_size=1)
        sb_items_padding.configure(adj, 1, 0)
        sb_items_padding.set_value(float(self.panel["items-padding"]))

        cb_icons = builder.get_object("icons")
        cb_icons.set_active_id(self.panel["icons"])

        eb_css_name = builder.get_object("css-name")
        eb_css_name.set_text(self.panel["css-name"])

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

    def lock_parent(self, w, parent):
        parent.hide()

    def release_parent(self, w, parent):
        parent.show()


def main():
    global configs
    configs = list_configs(config_dir)

    GLib.set_prgname('nwg-panel-config')

    global selector_window
    selector_window = PanelSelector()

    Gtk.main()


if __name__ == "__main__":
    sys.exit(main())
