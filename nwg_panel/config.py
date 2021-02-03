#!/usr/bin/python3

import os
import sys

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

from nwg_panel.tools import get_config_dir, load_json, list_outputs, check_key, is_command, list_configs

config_dir = get_config_dir()
configs = {}
editor = None
outputs = list_outputs()


def handle_keyboard(window, event):
    if event.type == Gdk.EventType.KEY_RELEASE and event.keyval == Gdk.KEY_Escape:
        window.close()


class PanelSelector(Gtk.Window):
    def __init__(self, parent):
        super(PanelSelector, self).__init__()
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_keep_above(True)
        self.connect("key-release-event", handle_keyboard)
        self.connect('destroy', self.release_parent, parent)

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
            label.set_text("File: {}".format(path))
            label.set_halign(Gtk.Align.START)
            grid.attach(label, 0, row, 3, 1)
            row += 1

            panels = configs[path]

            label = Gtk.Label()
            label.set_text("PANEL NAME")
            label.set_halign(Gtk.Align.START)
            grid.attach(label, 0, row, 1, 1)

            label = Gtk.Label()
            label.set_text("OUTPUT")
            label.set_halign(Gtk.Align.START)
            grid.attach(label, 1, row, 1, 1)

            label = Gtk.Label()
            label.set_text("POSITION")
            label.set_halign(Gtk.Align.START)
            grid.attach(label, 2, row, 1, 1)
            row += 1

            panel_idx = 0
            for panel in panels:
                check_key(panel, "name", "-")
                check_key(panel, "output", "-")
                check_key(panel, "position", "-")

                label = Gtk.Label()
                label.set_text(panel["name"])
                label.set_halign(Gtk.Align.START)
                grid.attach(label, 0, row, 1, 1)

                label = Gtk.Label()
                label.set_text(panel["output"])
                label.set_halign(Gtk.Align.START)
                grid.attach(label, 1, row, 1, 1)

                label = Gtk.Label()
                label.set_text(panel["position"])
                label.set_halign(Gtk.Align.START)
                grid.attach(label, 2, row, 1, 1)

                button = Gtk.Button.new_from_icon_name("document-edit", Gtk.IconSize.BUTTON)
                button.set_label("edit")
                button.connect("clicked", self.on_button_clicked, path, panel_idx)
                grid.attach(button, 3, row, 1, 1)

                row += 1
                panel_idx += 1

        self.show_all()
    
    def on_button_clicked(self, button, file, panel):
        editor.set_values(file, panel)
        self.close()
        
        
    def release_parent(self, w, parent):
        parent.set_sensitive(True)


class PanelEditor(object):
    def __init__(self):
        self.config = None
        self.panel = {}
        builder = Gtk.Builder()
        builder.add_from_file("glade/panel_edit.glade")
        self.lb_panel_desc = builder.get_object("label-desc")
        self.eb_name = builder.get_object("name")

        self.cb_output = builder.get_object("output")
        for key in outputs:
            self.cb_output.append(key, key)
        
        self.cb_position = builder.get_object("position")
        self.cb_layer = builder.get_object("layer")
        
        self.eb_width = builder.get_object("width")
        self.eb_height = builder.get_object("height")
        self.eb_margin_top = builder.get_object("margin-top")
        self.eb_margin_bottom = builder.get_object("margin-bottom")
        self.eb_padding_horizontal = builder.get_object("padding-horizontal")
        self.eb_padding_vertical = builder.get_object("padding-vertical")
        self.eb_spacing = builder.get_object("spacing")
        self.eb_items_padding = builder.get_object("items-padding")

        self.cb_icons = builder.get_object("icons")

        self.eb_css_name = builder.get_object("css-name")
        
        self.window = builder.get_object("panel_edit_win")
        self.window.connect('destroy', Gtk.main_quit)
        self.window.connect("key-release-event", handle_keyboard)
        self.window.set_sensitive(False)

        self.window.show_all()
        
    def set_values(self, file, panel_num):
        print(file, panel_num)
        self.config = load_json(file)
        self.panel = self.config[panel_num]
        check_key(self.panel, "name", "")
        check_key(self.panel, "output", "")
        check_key(self.panel, "position", "")
        
        check_key(self.panel, "width", "auto")
        check_key(self.panel, "height", 0)
        check_key(self.panel, "margin-top", 0)
        check_key(self.panel, "margin-bottom", 0)
        check_key(self.panel, "padding-horizontal", 0)
        check_key(self.panel, "padding-vertical", 0)
        check_key(self.panel, "spacing", 0)
        check_key(self.panel, "items-padding", 0)
        check_key(self.panel, "icons", "")
        check_key(self.panel, "css-name", "")
        
        #self.lb_panel_desc.set_text("Panel #{} in {}".format(panel_num, file))
        self.lb_panel_desc.set_text("Panel #{} in {}".format(panel_num, file))
        self.eb_name.set_text(self.panel["name"])

        self.cb_position.set_active_id(self.panel["position"])
        self.cb_layer.set_active_id(self.panel["layer"])
        
        self.eb_width.set_text(str(self.panel["width"]))
        self.eb_height.set_text(str(self.panel["height"]))
        self.eb_margin_top.set_text(str(self.panel["margin-top"]))
        self.eb_margin_bottom.set_text(str(self.panel["margin-bottom"]))
        self.eb_padding_horizontal.set_text(str(self.panel["padding-horizontal"]))
        self.eb_padding_vertical.set_text(str(self.panel["padding-vertical"]))
        self.eb_spacing.set_text(str(self.panel["spacing"]))
        self.eb_items_padding.set_text(str(self.panel["items-padding"]))

        if self.panel["icons"]:
            self.cb_icons.set_active_id(self.panel["icons"])
        else:
            self.cb_icons.set_active_id("gtk")
            
        if self.panel["output"] and self.panel["output"] in outputs:
            self.cb_output.set_active_id(self.panel["output"])
        
        self.eb_css_name.set_text(str(self.panel["css-name"]))


def main():
    global configs
    configs = list_configs(config_dir)

    GLib.set_prgname('nwg-panel-config')

    global editor
    editor = PanelEditor()
    selector = PanelSelector(editor.window)

    Gtk.main()


if __name__ == "__main__":
    sys.exit(main())
