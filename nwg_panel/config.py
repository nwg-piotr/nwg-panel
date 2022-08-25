#!/usr/bin/python3

import os
import signal
import subprocess
import sys
import time

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

from nwg_panel.tools import get_config_dir, local_dir, load_json, save_json, load_string, list_outputs, check_key, \
    list_configs, create_pixbuf, is_command, check_commands, cmd2string, eprint, temp_dir

from nwg_panel.__about__ import __version__

dir_name = os.path.dirname(__file__)

sway = os.getenv('SWAYSOCK') is not None

config_dir = get_config_dir()
data_home = os.getenv('XDG_DATA_HOME') if os.getenv('XDG_DATA_HOME') else os.path.join(os.getenv("HOME"),
                                                                                       ".local/share")
configs = {}
editor = None
selector_window = None
outputs = {}

SKELETON_PANEL: dict = {
    "name": "",
    "output": "",
    "layer": "bottom",
    "position": "top",
    "controls": "off",
    "menu-start": "off",
    "width": "auto",
    "height": 0,
    "margin-top": 0,
    "margin-bottom": 0,
    "padding-horizontal": 0,
    "padding-vertical": 0,
    "spacing": 0,
    "icons": "",
    "css-name": "",
    "modules-left": [],
    "modules-center": [],
    "modules-right": [],
    "controls-settings": {
        "components": ["net", "brightness", "volume", "battery"],
        "commands": {"net": "", "bluetooth": "", "battery": ""},
        "show-values": False,
        "interval": 1,
        "icon-size": 16,
        "hover-opens": True,
        "leave-closes": True,
        "root-css-name": "controls-overview",
        "css-name": "controls-window",
        "net-interface": "",
        "custom-items": [{"name": "Panel settings", "icon": "nwg-panel", "cmd": "nwg-panel-config"}],
        "menu": {"name": "unnamed", "icon": "", "items": []}
    },
    "menu-start-settings": {
        "cmd-lock": "swaylock -f -c 000000",
        "cmd-logout": "swaymsg exit",
        "cmd-restart": "systemctl reboot",
        "cmd-shutdown": "systemctl -i poweroff",
        "autohide": True,
        "file-manager": "thunar",
        "height": 0,
        "icon-size-large": 32,
        "icon-size-small": 16,
        "icon-size-button": 16,
        "margin-bottom": 0,
        "margin-left": 0,
        "margin-right": 0,
        "margin-top": 0,
        "padding": 2,
        "terminal": "foot",
        "width": 0
    },
    "sway-taskbar": {
        "workspace-menu": ["1", "2", "3", "4", "5", "6", "7", "8"],
        "name-max-len": 20,
        "image-size": 16,
        "workspaces-spacing": 0,
        "task-padding": 0,
        "show-app-icon": True,
        "show-app-name": True,
        "show-layout": True,
        "workspace-buttons": True,
        "all-workspaces": True,
        "mark-autotiling": True,
        "mark-xwayland": True,
        "all-outputs": False
    },
    "sway-workspaces": {
        "numbers": ["1", "2", "3", "4", "5", "6", "7", "8"],
        "show-icon": True,
        "image-size": 16,
        "show-name": True,
        "name-length": 40,
        "mark-autotiling": True,
        "mark-content": True,
        "show-layout": True
    },
    "clock": {
        "format": "%a, %d. %b  %H:%M:%S",
        "tooltip-text": "",
        "tooltip-date-format": False,
        "on-left-click": "",
        "on-middle-click": "",
        "on-right-click": "",
        "on-scroll-up": "",
        "on-scroll-down": "",
        "root-css-name": "root-clock",
        "css-name": "clock",
        "interval": 1,
        "angle": 0.0
    },
    "playerctl": {
        "buttons-position": "left",
        "icon-size": 16,
        "chars": 30,
        "button-css-name": "",
        "label-css-name": "",
        "interval": 1
    },
    "scratchpad": {
        "css-name": "",
        "icon-size": 16
    },
    "dwl-tags": {
        "tag-names": "1 2 3 4 5 6 7 8 9",
        "title-limit": 55
    },
    "openweather": {
        "appid": "",
        "weatherbit-api-key": "",
        "lat": None,
        "long": None,
        "lang": "en",
        "units": "metric",
        "interval": 1800,
        "loc-name": "",
        "weather-icons": "color",

        "on-right-click": "",
        "on-middle-click": "",
        "on-scroll": "",
        "icon-placement": "start",
        "icon-size": 24,
        "css-name": "weather",
        "show-name": False,
        "angle": 0.0,

        "ow-popup-icons": "light",
        "popup-icon-size": 24,
        "popup-text-size": "medium",
        "popup-css-name": "weather-forecast",
        "popup-placement": "right",
        "popup-margin-horizontal": 0,
        "popup-margin-top": 0,
        "popup-margin-bottom": 0,
        "show-humidity": True,
        "show-wind": True,
        "show-pressure": True,
        "show-cloudiness": True,
        "show-visibility": True,
        "show-pop": True,
        "show-volume": True
    },
    "brightness-slider": {
        "show-values": True,
        "icon-size": 16,
        "interval": 10,
        "hover-opens": False,
        "leave-closes": False,
        "root-css-name": "brightness-module",
        "css-name": "brightness-popup",
        "angle": 0.0,
        "icon-placement": "start",
        "backlight-device": "",
        "backlight-controller": "light",
        "slider-orientation": "horizontal",
        "slider-inverted": False,
        "popup-icon-placement": "start",
        "popup-horizontal-alignment": "left",
        "popup-vertical-alignment": "top",
        "popup-width": 256,
        "popup-height": 64,
        "popup-horizontal-margin": 0,
        "popup-vertical-margin": 0,
        "step-size": 1,
    }
}


def signal_handler(sig, frame):
    desc = {2: "SIGINT", 15: "SIGTERM"}
    if sig == 2 or sig == 15:
        print("Terminated with {}".format(desc[sig]))
        Gtk.main_quit()
    else:
        print("{} signal received".format(sig))


def handle_keyboard(window, event):
    if event.type == Gdk.EventType.KEY_RELEASE and event.keyval == Gdk.KEY_Escape:
        window.close()


class PanelSelector(Gtk.Window):
    def __init__(self):
        super(PanelSelector, self).__init__()
        self.to_delete = []
        self.connect("key-release-event", handle_keyboard)
        self.connect('destroy', Gtk.main_quit)
        self.plugin_menu_start = is_command("nwg-menu")

        self.outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(self.outer_box)

        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_propagate_natural_width(True)
        self.scrolled_window.set_propagate_natural_height(True)
        self.scrolled_window.set_property("margin-top", 6)
        max_height = 0
        for key in outputs:
            h = outputs[key]["height"]
            if max_height == 0:
                max_height = h
            if not h > max_height:
                max_height = h
        self.scrolled_window.set_max_content_height(int(max_height * 0.9))
        self.outer_box.add(self.scrolled_window)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.scrolled_window.add(vbox)

        self.hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        vbox.pack_start(self.hbox, True, False, 6)
        listboxes = self.build_listboxes()
        self.hbox.pack_start(listboxes, True, True, 6)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        logo = Gtk.Image.new_from_icon_name("nwg-panel", Gtk.IconSize.LARGE_TOOLBAR)
        logo.set_property("margin-left", 12)
        hbox.pack_start(logo, False, False, 0)
        label = Gtk.Label()
        try:
            ver = __version__
        except:
            ver = ""
        label.set_markup('<b>nwg-panel</b> v{} <a href="https://github.com/nwg-piotr/nwg-panel">GitHub</a>'.format(ver))
        hbox.pack_start(label, False, False, 0)

        self.outer_box.pack_end(hbox, False, False, 18)

        inner_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox.pack_start(inner_hbox, True, True, 12)

        label = Gtk.Label()
        label.set_text("New file:")
        label.set_halign(Gtk.Align.START)
        inner_hbox.pack_start(label, False, False, 6)

        self.new_file_entry = Gtk.Entry()
        self.new_file_entry.set_width_chars(15)
        self.new_file_entry.set_placeholder_text("filename")
        self.new_file_entry.connect("changed", validate_name)
        inner_hbox.pack_start(self.new_file_entry, False, False, 0)

        btn = Gtk.Button.new_with_label("Add/delete")
        btn.connect("clicked", self.add_delete_files)
        inner_hbox.pack_end(btn, False, False, 0)

        btn = Gtk.Button.new_with_label("Close")
        btn.connect("clicked", Gtk.main_quit)
        inner_hbox.pack_end(btn, False, False, 0)

        self.show_all()

        self.connect("show", self.refresh)

    def refresh(self, *args, reload=True):
        if reload:
            global configs
            configs = list_configs(config_dir)

        for item in self.hbox.get_children():
            item.destroy()
        listboxes = self.build_listboxes()
        self.hbox.pack_start(listboxes, True, True, 20)

        self.new_file_entry.set_text("")

        self.show_all()

    def build_listboxes(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        for path in configs:
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            label = Gtk.Label()
            label.set_text(path)
            label.set_halign(Gtk.Align.START)
            hbox.pack_start(label, True, True, 6)
            checkbox = Gtk.CheckButton.new_with_label("delete file")
            checkbox.connect("toggled", self.mark_to_delete, path)
            hbox.pack_end(checkbox, False, False, 0)
            vbox.pack_start(hbox, False, False, 10)

            panels = configs[path]
            panel_idx = 0
            for panel in panels:
                for item in ["name", "output", "position"]:
                    check_key(panel, item, "")
                listbox = Gtk.ListBox()
                listbox.set_selection_mode(Gtk.SelectionMode.NONE)
                vbox.add(listbox)

                row = Gtk.ListBoxRow()
                ivbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                lbl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                lbl_box.set_homogeneous(True)
                hbox.pack_start(lbl_box, True, True, 0)

                ivbox.pack_start(hbox, False, False, 3)

                label = Gtk.Label()
                label.set_text("{}                ".format(panel["name"])[:20])
                label.set_halign(Gtk.Align.START)
                lbl_box.pack_start(label, True, True, 6)

                label = Gtk.Label()
                label.set_text(panel["output"])
                label.set_halign(Gtk.Align.START)
                lbl_box.pack_start(label, True, True, 6)

                label = Gtk.Label()
                label.set_text(panel["position"])
                label.set_halign(Gtk.Align.START)
                lbl_box.pack_start(label, True, True, 6)

                btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

                btn = Gtk.Button.new_from_icon_name("go-up", Gtk.IconSize.MENU)
                btn.set_always_show_image(True)
                if panel_idx > 0:
                    btn.set_tooltip_text("Move up")
                btn.set_sensitive(panel_idx > 0)
                btn.connect("clicked", self.move_up, panels, panels[panel_idx])
                btn_box.pack_start(btn, False, False, 0)

                btn = Gtk.Button.new_from_icon_name("go-down", Gtk.IconSize.MENU)
                btn.set_always_show_image(True)
                if panel_idx < len(panels) - 1:
                    btn.set_tooltip_text("Move down")
                btn.set_sensitive(panel_idx < len(panels) - 1)
                btn.connect("clicked", self.move_down, panels, panels[panel_idx])
                btn_box.pack_start(btn, False, False, 0)

                btn = Gtk.Button.new_from_icon_name("list-remove", Gtk.IconSize.MENU)
                btn.set_always_show_image(True)
                btn.set_tooltip_text("Remove panel")
                btn.connect("clicked", self.delete, panels, panels[panel_idx])
                btn_box.pack_start(btn, False, False, 0)

                btn = Gtk.Button.new_from_icon_name("document-edit", Gtk.IconSize.BUTTON)
                btn.connect("clicked", self.on_edit_button, path, panel_idx)
                btn.set_tooltip_text("Edit panel")
                btn_box.pack_start(btn, False, False, 0)

                hbox.pack_end(btn_box, False, False, 6)

                row.add(ivbox)
                listbox.add(row)
                panel_idx += 1

            listbox = Gtk.ListBox()
            listbox.set_selection_mode(Gtk.SelectionMode.NONE)
            vbox.add(listbox)

            row = Gtk.ListBoxRow()
            ivbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            ivbox.pack_start(hbox, False, False, 3)
            btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

            btn = Gtk.Button.new_from_icon_name("list-add", Gtk.IconSize.MENU)
            btn.set_always_show_image(True)
            btn.set_label("New")
            btn.connect("clicked", self.append, path)
            btn_box.pack_start(btn, False, False, 0)

            btn = Gtk.Button.new_from_icon_name("object-select", Gtk.IconSize.MENU)
            btn.set_always_show_image(True)
            btn.set_label("Apply")
            btn_box.pack_start(btn, False, False, 0)
            btn.connect("clicked", self.apply, panels, path)
            hbox.pack_end(btn_box, False, False, 6)
            row.add(ivbox)
            listbox.add(row)

        return vbox

    def mark_to_delete(self, cb, file):
        if cb.get_active():
            if file not in self.to_delete:
                self.to_delete.append(file)
        else:
            if file in self.to_delete:
                self.to_delete.remove(file)

    def add_delete_files(self, btn):
        for file in self.to_delete:
            os.remove(file)
        self.to_delete = []

        if self.new_file_entry.get_text():
            config = []
            save_json(config, os.path.join(config_dir, self.new_file_entry.get_text()))

        self.refresh()

    def on_edit_button(self, button, file, panel_idx):
        global editor
        editor = EditorWrapper(self, file, panel_idx, self.plugin_menu_start)
        editor.edit_panel()

    def move_up(self, btn, panels, panel):
        old_index = panels.index(panel)
        panels.insert(old_index - 1, panels.pop(old_index))
        self.refresh(reload=False)

    def move_down(self, btn, panels, panel):
        old_index = panels.index(panel)
        panels.insert(old_index + 1, panels.pop(old_index))
        self.refresh(reload=False)

    def delete(self, btn, panels, panel):
        panels.remove(panel)
        self.refresh(reload=False)

    def append(self, btn, file):
        config = load_json(file)
        panel = SKELETON_PANEL
        config.append(panel)
        idx = config.index(panel)
        save_json(config, file)
        global editor
        editor = EditorWrapper(self, file, idx, self.plugin_menu_start)
        editor.set_panel()
        editor.edit_panel()

    def apply(self, btn, panels, path):
        save_json(panels, path)
        self.refresh()


def validate_workspaces(gtk_entry):
    valid_text = ""
    for char in gtk_entry.get_text():
        if char.isdigit() or char == " ":
            valid_text += char
    while '  ' in valid_text:
        valid_text = valid_text.replace('  ', ' ')
    gtk_entry.set_text(valid_text)


def validate_name(gtk_entry):
    valid_text = ""
    for char in gtk_entry.get_text():
        if char == " ":
            char = "-"
        if char.isalnum() or char in ["-", "_"]:
            valid_text += char.lower()
        while '--' in valid_text:
            valid_text = valid_text.replace('--', '-')
    gtk_entry.set_text(valid_text)


def update_icon(gtk_entry, icons):
    icons_path = ""
    if icons == "light":
        icons_path = os.path.join(get_config_dir(), "icons_light")
    elif icons == "dark":
        icons_path = os.path.join(get_config_dir(), "icons_dark")
    name = gtk_entry.get_text()
    gtk_entry.set_icon_from_pixbuf(Gtk.EntryIconPosition.PRIMARY, create_pixbuf(name, 16, icons_path=icons_path))


def switch_entry_visibility(checkbutton, entry):
    entry.set_visibility(checkbutton.get_active())


class EditorWrapper(object):
    def __init__(self, parent, file, panel_idx, plugin_menu_start):
        self.file = file
        self.panel_idx = panel_idx
        self.config = {}
        self.panel = {}
        self.executors_base = {}
        self.executors_file = os.path.join(local_dir(), "executors.json")
        self.executors_base = load_json(self.executors_file) if os.path.isfile(self.executors_file) else {}
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(dir_name, "glade/config_main.glade"))

        self.window = builder.get_object("main-window")
        # self.window.set_transient_for(parent)
        self.window.set_keep_above(True)
        self.window.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.window.connect('destroy', self.show_parent, parent)
        self.window.connect("key-release-event", handle_keyboard)
        self.window.connect("show", self.hide_parent, parent)

        self.delete_weather_data = False

        Gtk.Widget.set_size_request(self.window, 677, 1)

        self.known_modules = ["clock",
                              "playerctl",
                              "sway-taskbar",
                              "sway-workspaces",
                              "scratchpad",
                              "openweather",
                              "brightness-slider",
                              "dwl-tags",
                              "tray"]

        self.scrolled_window = builder.get_object("scrolled-window")

        eb = builder.get_object("eb-panel")
        eb.connect("button-press-event", self.edit_panel)

        eb = builder.get_object("eb-modules-left")
        eb.connect("button-press-event", self.edit_modules, "left")

        eb = builder.get_object("eb-modules-center")
        eb.connect("button-press-event", self.edit_modules, "center")

        eb = builder.get_object("eb-modules-right")
        eb.connect("button-press-event", self.edit_modules, "right")

        eb = builder.get_object("eb-controls")
        eb.connect("button-press-event", self.controls_menu)

        eb = builder.get_object("eb-swaync")
        if is_command("swaync"):
            eb.connect("button-press-event", self.edit_swaync)
        else:
            eb.set_sensitive(False)
            eb.set_tooltip_text("'swaync' package required")

        eb = builder.get_object("eb-tray")
        try:
            import dasbus
            eb.connect("button-press-event", self.edit_tray)
        except ModuleNotFoundError:
            eb.set_sensitive(False)
            eb.set_tooltip_text("'python-dasbus' package required")

        eb = builder.get_object("eb-clock")
        eb.connect("button-press-event", self.edit_clock)

        eb = builder.get_object("eb-playerctl")
        eb.connect("button-press-event", self.edit_playerctl)

        eb = builder.get_object("eb-sway-taskbar")
        eb.connect("button-press-event", self.edit_sway_taskbar)

        eb = builder.get_object("eb-sway-workspaces")
        eb.connect("button-press-event", self.edit_sway_workspaces)

        eb = builder.get_object("eb-scratchpad")
        eb.connect("button-press-event", self.edit_scratchpad)

        eb = builder.get_object("eb-openweather")
        eb.connect("button-press-event", self.edit_openweather)

        eb = builder.get_object("eb-brightness-slider")
        eb.connect("button-press-event", self.edit_brightness_slider)

        eb = builder.get_object("eb-dwl-tags")
        eb.connect("button-press-event", self.edit_dwl_tags)

        eb = builder.get_object("eb-executors")
        eb.connect("button-press-event", self.select_executor)

        eb = builder.get_object("eb-buttons")
        eb.connect("button-press-event", self.select_button)

        eb = builder.get_object("eb-menu-start")
        if plugin_menu_start:
            eb.connect("button-press-event", self.edit_menu_start)
        else:
            eb.set_sensitive(False)
            eb.set_tooltip_text("'nwg-menu' package required")

        btn = builder.get_object("btn-close")
        btn.connect("clicked", self.quit)

        btn = builder.get_object("btn-apply")
        btn.connect("clicked", self.apply_changes)

        btn = builder.get_object("btn-apply-restart")
        btn.connect("clicked", self.restart_panel)

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
        self.panel_name_label = builder.get_object("panel-name-label")
        self.panel_name_label.set_text("Editing: '{}'".format(self.panel["name"]))

        self.edit_panel()

        self.window.show_all()

    def quit(self, btn):
        selector_window.show_all()
        self.window.close()

    def load_panel(self):
        if self.panel_idx is not None:
            self.config = load_json(self.file)
            self.panel = self.config[self.panel_idx]
        else:
            self.config = []
            self.panel = SKELETON_PANEL
            self.config.append(self.panel)
            self.panel_idx = self.config.index(self.panel)
            save_json(self.config, self.file)

        self.check_defaults()

    def set_panel(self):
        if self.file:
            self.load_panel()
        else:
            self.panel = SKELETON_PANEL

        self.check_defaults()

    def check_defaults(self):
        defaults = {
            "name": "",
            "output": "",
            "layer": "bottom",
            "position": "top",
            "controls": "off",
            "menu-start": "off",
            "width": "auto",
            "height": 0,
            "margin-top": 0,
            "margin-bottom": 0,
            "padding-horizontal": 0,
            "padding-vertical": 0,
            "spacing": 0,
            "icons": "",
            "css-name": "",
            "exclusive-zone": True
        }
        for key in defaults:
            check_key(self.panel, key, defaults[key])

        for key in self.known_modules:
            check_key(self.panel, key, {})

    def edit_panel(self, *args):
        self.check_defaults()
        self.edited = "panel"
        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_panel.glade"))
        frame = builder.get_object("frame")

        self.eb_name = builder.get_object("name")
        self.eb_name.set_text(self.panel["name"])
        self.eb_name.connect("changed", validate_name)

        self.cb_output = builder.get_object("output")
        for key in outputs:
            self.cb_output.append(key, key)

        self.cb_output.append("All", "All")

        if self.panel["output"] and (self.panel["output"] in outputs or self.panel["output"] == "All"):
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

        self.cb_menu = builder.get_object("menu")
        if not self.panel["menu-start"]:
            self.cb_menu.set_active_id("off")
        else:
            if self.panel["menu-start"] == "right":
                self.cb_menu.set_active_id("right")
            elif self.panel["menu-start"] == "left":
                self.cb_menu.set_active_id("left")
            else:
                self.cb_menu.set_active_id("off")

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

        self.cb_exclusive_zone = builder.get_object("exclusive-zone")
        self.cb_exclusive_zone.set_active(self.panel["exclusive-zone"])

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(frame)

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

        val = self.cb_menu.get_active_id()
        if val:
            if val in ["left", "right"]:
                self.panel["menu-start"] = val
            else:
                self.panel["menu-start"] = "off"

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
        self.panel["css-name"] = val

        self.panel["exclusive-zone"] = self.cb_exclusive_zone.get_active()

        save_json(self.config, self.file)

    def hide_parent(self, w, parent):
        parent.set_sensitive(False)

    def show_parent(self, w, parent):
        parent.set_sensitive(True)

    def apply_changes(self, *args):
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
        elif self.edited == "scratchpad":
            self.update_scratchpad()
        elif self.edited == "executor":
            self.update_executor()
        elif self.edited == "swaync":
            self.update_swaync()
        elif self.edited == "tray":
            self.update_tray()
        elif self.edited == "button":
            self.update_button()
        elif self.edited == "modules":
            save_json(self.config, self.file)
        elif self.edited == "controls":
            self.update_controls()
        elif self.edited == "menu-start":
            self.update_menu_start()
        elif self.edited == "dwl-tags":
            self.update_dwl_tags()
        elif self.edited == "openweather":
            self.update_openweather()
        elif self.edited == "brightness-slider":
            self.update_brightness_slider()
        elif self.edited == "custom-items":
            save_json(self.config, self.file)
        elif self.edited == "user-menu":
            save_json(self.config, self.file)

        if self.delete_weather_data:
            tmp_dir = temp_dir()
            for item in ["nwg-openweather-weather", "nwg-openweather-forecast", "nwg-weatherbit-alerts"]:
                f = "{}-{}".format(os.path.join(tmp_dir, item), self.panel["openweather"]["module-id"])
                if os.path.exists(f):
                    eprint("Deleting {}".format(f))
                    os.remove(f)
                else:
                    eprint("{} file not found".format(f))

        self.panel_name_label.set_text("Editing: '{}'".format(self.panel["name"]))
        selector_window.refresh(reload=True)

    def restart_panel(self, *args):
        self.apply_changes()

        cmd = "nwg-panel"
        try:
            args_string = load_string(os.path.join(local_dir(), "args"))
            cmd = "nwg-panel {}".format(args_string)
        except:
            pass

        print("Restarting panels".format(cmd))
        subprocess.Popen('exec {}'.format(cmd), shell=True)

    def edit_sway_taskbar(self, *args):
        self.load_panel()
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
            "all-workspaces": True,
            "mark-autotiling": True,
            "mark-xwayland": True,
            "all-outputs": False,
            "angle": 0.0,
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_sway_taskbar.glade"))
        frame = builder.get_object("frame")

        self.eb_workspace_menu = builder.get_object("workspace-menu")
        workspaces = settings["workspace-menu"]
        text = ""
        for item in workspaces:
            text += str(item) + " "
        self.eb_workspace_menu.set_text(text.strip())
        self.eb_workspace_menu.connect("changed", validate_workspaces)

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

        self.ckb_all_workspaces = builder.get_object("all-workspaces")
        self.ckb_all_workspaces.set_active(settings["all-workspaces"])

        self.ckb_mark_autotiling = builder.get_object("mark-autotiling")
        self.ckb_mark_autotiling.set_active(settings["mark-autotiling"])

        self.ckb_mark_xwayland = builder.get_object("mark-xwayland")
        self.ckb_mark_xwayland.set_active(settings["mark-xwayland"])

        self.ckb_all_outputs = builder.get_object("all-outputs")
        self.ckb_all_outputs.set_active(settings["all-outputs"])

        self.taskbar_angle = builder.get_object("angle")
        self.taskbar_angle.set_active_id(str(settings["angle"]))

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(frame)

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

        settings["show-app-icon"] = self.ckb_show_app_icon.get_active()

        settings["show-app-name"] = self.ckb_show_app_name.get_active()

        settings["show-layout"] = self.ckb_show_layout.get_active()

        settings["workspace-buttons"] = self.workspace_buttons.get_active()

        settings["all-workspaces"] = self.ckb_all_workspaces.get_active()

        settings["mark-autotiling"] = self.ckb_mark_autotiling.get_active()

        settings["mark-xwayland"] = self.ckb_mark_xwayland.get_active()

        settings["all-outputs"] = self.ckb_all_outputs.get_active()

        try:
            settings["angle"] = float(self.taskbar_angle.get_active_id())
        except:
            settings["angle"] = 0.0

        save_json(self.config, self.file)

    def edit_clock(self, *args):
        self.load_panel()
        self.edited = "clock"
        check_key(self.panel, "clock", {})
        settings = self.panel["clock"]
        defaults = {
            "format": "%a, %d. %b  %H:%M:%S",
            "tooltip-text": "",
            "tooltip-date-format": False,
            "on-left-click": "",
            "on-middle-click": "",
            "on-right-click": "",
            "on-scroll-up": "",
            "on-scroll-down": "",
            "root-css-name": "root-clock",
            "css-name": "clock",
            "interval": 1,
            "angle": 0.0,
            "calendar-path": "",
            "calendar-css-name": "calendar-window",
            "calendar-placement": "top",
            "calendar-margin-horizontal": 0,
            "calendar-margin-vertical": 0,
            "calendar-icon-size": 24,
            "calendar-interval": 60,
            "calendar-on": True
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_clock.glade"))
        frame = builder.get_object("frame")

        self.eb_format = builder.get_object("format")
        self.eb_format.set_text(settings["format"])

        self.eb_tooltip_text = builder.get_object("tooltip-text")
        self.eb_tooltip_text.set_text(settings["tooltip-text"])

        self.eb_tooltip_date = builder.get_object("tooltip-date")
        self.eb_tooltip_date.set_active(settings["tooltip-date-format"])

        self.eb_on_middle_click = builder.get_object("on-middle-click")
        self.eb_on_middle_click.set_text(settings["on-middle-click"])

        self.eb_on_right_click = builder.get_object("on-right-click")
        self.eb_on_right_click.set_text(settings["on-right-click"])

        self.eb_on_scroll_up = builder.get_object("on-scroll-up")
        self.eb_on_scroll_up.set_text(settings["on-scroll-up"])

        self.eb_on_scroll_down = builder.get_object("on-scroll-down")
        self.eb_on_scroll_down.set_text(settings["on-scroll-down"])

        self.eb_root_css_name_clock = builder.get_object("root-css-name")
        self.eb_root_css_name_clock.set_text(settings["root-css-name"])

        self.eb_css_name_clock = builder.get_object("css-name")
        self.eb_css_name_clock.set_text(settings["css-name"])

        self.sb_interval = builder.get_object("interval")
        self.sb_interval.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=1, upper=3600, step_increment=1, page_increment=10, page_size=1)
        self.sb_interval.configure(adj, 1, 0)
        self.sb_interval.set_value(settings["interval"])

        self.cb_angle = builder.get_object("angle")
        self.cb_angle.set_active_id(str(settings["angle"]))

        self.cb_calendar_on = builder.get_object("calendar-on")
        self.cb_calendar_on.set_active(settings["calendar-on"])

        self.combo_calendar_placement = builder.get_object("calendar-placement")
        self.combo_calendar_placement.set_active_id(settings["calendar-placement"])

        self.sb_calendar_margin_horizontal = builder.get_object("calendar-margin-horizontal")
        self.sb_calendar_margin_horizontal.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=0, upper=720, step_increment=1, page_increment=10, page_size=1)
        self.sb_calendar_margin_horizontal.configure(adj, 1, 0)
        self.sb_calendar_margin_horizontal.set_value(settings["calendar-margin-horizontal"])

        self.sb_calendar_margin_vertical = builder.get_object("calendar-margin-vertical")
        self.sb_calendar_margin_vertical.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=0, upper=480, step_increment=1, page_increment=10, page_size=1)
        self.sb_calendar_margin_vertical.configure(adj, 1, 0)
        self.sb_calendar_margin_vertical.set_value(settings["calendar-margin-vertical"])

        self.eb_calendar_css_name = builder.get_object("calendar-css-name")
        self.eb_calendar_css_name.set_text(settings["calendar-css-name"])

        self.eb_calendar_path = builder.get_object("calendar-path")
        self.eb_calendar_path.set_text(settings["calendar-path"])

        self.sb_calendar_icon_size = builder.get_object("calendar-icon-size")
        self.sb_calendar_icon_size.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=8, upper=512, step_increment=1, page_increment=10, page_size=1)
        self.sb_calendar_icon_size.configure(adj, 1, 0)
        self.sb_calendar_icon_size.set_value(settings["calendar-icon-size"])

        self.sb_calendar_interval = builder.get_object("calendar-interval")
        self.sb_calendar_interval.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=60, upper=86400, step_increment=1, page_increment=10, page_size=1)
        self.sb_calendar_interval.configure(adj, 1, 0)
        self.sb_calendar_interval.set_value(settings["calendar-interval"])

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(frame)

    def update_clock(self):
        settings = self.panel["clock"]

        settings["format"] = self.eb_format.get_text()
        settings["tooltip-text"] = self.eb_tooltip_text.get_text()
        settings["tooltip-date-format"] = self.eb_tooltip_date.get_active()
        settings["on-middle-click"] = self.eb_on_middle_click.get_text()
        settings["on-right-click"] = self.eb_on_right_click.get_text()

        settings["on-scroll-up"] = self.eb_on_scroll_up.get_text()
        settings["on-scroll-down"] = self.eb_on_scroll_down.get_text()
        settings["root-css-name"] = self.eb_root_css_name_clock.get_text()
        settings["css-name"] = self.eb_css_name_clock.get_text()

        try:
            settings["angle"] = float(self.cb_angle.get_active_id())
        except:
            settings["angle"] = 0.0

        val = self.sb_interval.get_value()
        if val is not None:
            settings["interval"] = int(val)

        settings["calendar-on"] = self.cb_calendar_on.get_active()
        settings["calendar-path"] = self.eb_calendar_path.get_text()
        settings["calendar-placement"] = self.combo_calendar_placement.get_active_id()
        settings["calendar-margin-horizontal"] = int(self.sb_calendar_margin_horizontal.get_value())
        settings["calendar-margin-vertical"] = int(self.sb_calendar_margin_vertical.get_value())
        settings["calendar-css-name"] = self.eb_calendar_css_name.get_text()
        settings["calendar-icon-size"] = int(self.sb_calendar_icon_size.get_value())
        settings["calendar-interval"] = int(self.sb_calendar_interval.get_value())

        save_json(self.config, self.file)

    def edit_swaync(self, *args):
        self.load_panel()
        self.edited = "swaync"
        check_key(self.panel, "swaync", {})
        settings = self.panel["swaync"]

        defaults = {
            "tooltip-text": "Notifications",
            "on-left-click": "swaync-client -t",
            "on-middle-click": "",
            "on-right-click": "",
            "on-scroll-up": "",
            "on-scroll-down": "",
            "root-css-name": "root-executor",
            "css-name": "executor",
            "icon-placement": "left",
            "icon-size": 18,
            "interval": 1,
            "always-show-icon": True
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_swaync.glade"))
        frame = builder.get_object("frame")

        self.nc_tooltip_text = builder.get_object("tooltip-text")
        self.nc_tooltip_text.set_text(settings["tooltip-text"])

        self.nc_on_middle_click = builder.get_object("on-middle-click")
        self.nc_on_middle_click.set_text(settings["on-middle-click"])

        self.nc_on_right_click = builder.get_object("on-right-click")
        self.nc_on_right_click.set_text(settings["on-right-click"])

        self.nc_on_scroll_up = builder.get_object("on-scroll-up")
        self.nc_on_scroll_up.set_text(settings["on-scroll-up"])

        self.nc_on_scroll_down = builder.get_object("on-scroll-down")
        self.nc_on_scroll_down.set_text(settings["on-scroll-down"])

        self.nc_root_css_name = builder.get_object("root-css-name")
        self.nc_root_css_name.set_text(settings["root-css-name"])

        self.nc_css_name = builder.get_object("css-name")
        self.nc_css_name.set_text(settings["css-name"])

        self.nc_icon_placement = builder.get_object("icon-placement")
        self.nc_icon_placement.set_active_id(settings["icon-placement"])

        self.nc_icon_size = builder.get_object("icon-size")
        self.nc_icon_size.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=8, upper=128, step_increment=1, page_increment=10, page_size=1)
        self.nc_icon_size.configure(adj, 1, 0)
        self.nc_icon_size.set_value(settings["icon-size"])

        self.nc_interval = builder.get_object("interval")
        self.nc_interval.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=1, upper=3600, step_increment=1, page_increment=10, page_size=1)
        self.nc_interval.configure(adj, 1, 0)
        self.nc_interval.set_value(settings["interval"])

        self.nc_always_show_icon = builder.get_object("always-show-icon")
        self.nc_always_show_icon.set_active(settings["always-show-icon"])

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(frame)

    def update_swaync(self):
        settings = self.panel["swaync"]

        settings["tooltip-text"] = self.nc_tooltip_text.get_text()
        settings["on-middle-click"] = self.nc_on_middle_click.get_text()
        settings["on-right-click"] = self.nc_on_right_click.get_text()
        settings["on-scroll-up"] = self.nc_on_scroll_up.get_text()
        settings["on-scroll-down"] = self.nc_on_scroll_down.get_text()
        settings["root-css-name"] = self.nc_root_css_name.get_text()
        settings["css-name"] = self.nc_css_name.get_text()

        val = self.nc_interval.get_value()
        if val is not None:
            settings["interval"] = int(val)

        if self.nc_icon_placement.get_active_id():
            settings["icon-placement"] = self.nc_icon_placement.get_active_id()

        settings["icon-size"] = int(self.nc_icon_size.get_value())
        settings["interval"] = int(self.nc_interval.get_value())
        settings["always-show-icon"] = self.nc_always_show_icon.get_active()

        save_json(self.config, self.file)

    def edit_tray(self, *args):
        self.load_panel()
        self.edited = "tray"
        check_key(self.panel, "tray", {})
        settings = self.panel["tray"]

        defaults = {
            "icon-size": 16,
            "root-css-name": "tray",
            "inner-css-name": "inner-tray",
            "smooth-scrolling-threshold": 0
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_tray.glade"))
        frame = builder.get_object("frame")

        self.nc_icon_size = builder.get_object("icon-size")
        self.nc_icon_size.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=8, upper=128, step_increment=1, page_increment=10, page_size=1)
        self.nc_icon_size.configure(adj, 1, 0)
        self.nc_icon_size.set_value(settings["icon-size"])

        self.nc_root_css_name = builder.get_object("root-css-name")
        self.nc_root_css_name.set_text(settings["root-css-name"])

        self.nc_inner_css_name = builder.get_object("inner-css-name")
        self.nc_inner_css_name.set_text(settings["inner-css-name"])

        self.nc_smooth_scrolling_threshold = builder.get_object("smooth-scrolling-threshold")
        self.nc_smooth_scrolling_threshold.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=0, upper=3600, step_increment=1, page_increment=10, page_size=1)
        self.nc_smooth_scrolling_threshold.configure(adj, 1, 0)
        self.nc_smooth_scrolling_threshold.set_value(settings["smooth-scrolling-threshold"])

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(frame)

    def update_tray(self):
        settings = self.panel["tray"]

        settings["icon-size"] = int(self.nc_icon_size.get_value())
        settings["root-css-name"] = self.nc_root_css_name.get_text()
        settings["inner-css-name"] = self.nc_inner_css_name.get_text()
        settings["smooth-scrolling-threshold"] = int(self.nc_smooth_scrolling_threshold.get_value())

        save_json(self.config, self.file)

    def edit_playerctl(self, *args):
        self.load_panel()
        self.edited = "playerctl"
        check_key(self.panel, "playerctl", {})
        settings = self.panel["playerctl"]
        defaults = {
            "buttons-position": "left",
            "icon-size": 16,
            "chars": 30,
            "button-css-name": "",
            "label-css-name": "",
            "interval": 1,
            "angle": 0.0
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_playerctl.glade"))
        frame = builder.get_object("frame")

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

        self.plctl_angle = builder.get_object("angle")
        self.plctl_angle.set_active_id(str(settings["angle"]))

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(frame)

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

        try:
            settings["angle"] = float(self.plctl_angle.get_active_id())
        except:
            settings["angle"] = 0.0

        save_json(self.config, self.file)

    def edit_sway_workspaces(self, *args):
        self.load_panel()
        self.edited = "sway-workspaces"
        check_key(self.panel, "sway-workspaces", {})
        settings = self.panel["sway-workspaces"]
        defaults = {
            "numbers": [1, 2, 3, 4, 5, 6, 7, 8],
            "custom-labels": [],
            "focused-labels": [],
            "show-icon": True,
            "image-size": 16,
            "show-name": True,
            "name-length": 40,
            "mark-autotiling": True,
            "mark-content": True,
            "show-layout": True,
            "angle": 0.0
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_sway_workspaces.glade"))
        frame = builder.get_object("frame")

        self.eb_workspaces_menu = builder.get_object("numbers")
        workspaces = settings["numbers"]
        text = ""
        for item in workspaces:
            text += str(item) + " "
        self.eb_workspaces_menu.set_text(text.strip())
        self.eb_workspaces_menu.connect("changed", validate_workspaces)

        self.ws_custom_labels = builder.get_object("custom-labels")
        labels = settings["custom-labels"]
        text = ""
        for item in labels:
            text += str(item) + " "
        self.ws_custom_labels.set_text(text.strip())

        self.ws_focused_labels = builder.get_object("focused-labels")
        labels = settings["focused-labels"]
        text = ""
        for item in labels:
            text += str(item) + " "
        self.ws_focused_labels.set_text(text.strip())

        self.ws_show_icon = builder.get_object("show-icon")
        self.ws_show_icon.set_active(settings["show-icon"])

        self.ws_show_name = builder.get_object("show-name")
        self.ws_show_name.set_active(settings["show-name"])

        self.ws_image_size = builder.get_object("image-size")
        self.ws_image_size.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=8, upper=129, step_increment=1, page_increment=10, page_size=1)
        self.ws_image_size.configure(adj, 1, 0)
        self.ws_image_size.set_value(settings["image-size"])

        self.ws_name_length = builder.get_object("name-length")
        self.ws_name_length.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=1, upper=256, step_increment=1, page_increment=10, page_size=1)
        self.ws_name_length.configure(adj, 1, 0)
        self.ws_name_length.set_value(settings["name-length"])

        self.ws_mark_autotiling = builder.get_object("mark-autotiling")
        self.ws_mark_autotiling.set_active(settings["mark-autotiling"])

        self.ws_mark_content = builder.get_object("mark-content")
        self.ws_mark_content.set_active(settings["mark-content"])

        self.ws_show_layout = builder.get_object("show-layout")
        self.ws_show_layout.set_active(settings["show-layout"])

        self.ws_angle = builder.get_object("angle")
        self.ws_angle.set_active_id(str(settings["angle"]))

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(frame)

    def update_sway_workspaces(self):
        settings = self.panel["sway-workspaces"]

        val = self.eb_workspaces_menu.get_text()
        if val:
            settings["numbers"] = val.split()

        val = self.ws_custom_labels.get_text()
        settings["custom-labels"] = val.split()

        val = self.ws_focused_labels.get_text()
        settings["focused-labels"] = val.split()

        val = self.ws_show_icon.get_active()
        if val is not None:
            settings["show-icon"] = val

        val = self.ws_show_name.get_active()
        if val is not None:
            settings["show-name"] = val

        settings["image-size"] = int(self.ws_image_size.get_value())

        settings["name-length"] = int(self.ws_name_length.get_value())

        val = self.ws_mark_autotiling.get_active()
        if val is not None:
            settings["mark-autotiling"] = val

        val = self.ws_mark_content.get_active()
        if val is not None:
            settings["mark-content"] = val

        val = self.ws_show_layout.get_active()
        if val is not None:
            settings["show-layout"] = val

        try:
            settings["angle"] = float(self.ws_angle.get_active_id())
        except:
            settings["angle"] = 0.0

        save_json(self.config, self.file)

    def edit_menu_start(self, *args):
        self.load_panel()
        self.edited = "menu-start"
        check_key(self.panel, "menu-start-settings", {})
        settings = self.panel["menu-start-settings"]
        defaults = {
            "cmd-lock": "swaylock -f -c 000000",
            "cmd-logout": "swaymsg exit",
            "cmd-restart": "systemctl reboot",
            "cmd-shutdown": "systemctl -i poweroff",
            "autohide": True,
            "file-manager": "thunar",
            "height": 0,
            "icon-size-large": 32,
            "icon-size-small": 16,
            "icon-size-button": 16,
            "margin-bottom": 0,
            "margin-left": 0,
            "margin-right": 0,
            "margin-top": 0,
            "padding": 2,
            "terminal": "foot",
            "width": 0
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_menu_start.glade"))
        frame = builder.get_object("frame")

        self.ms_window_width = builder.get_object("width")
        self.ms_window_width.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=0, upper=1921, step_increment=1, page_increment=10, page_size=1)
        self.ms_window_width.configure(adj, 1, 0)
        self.ms_window_width.set_value(settings["width"])

        self.ms_window_height = builder.get_object("height")
        self.ms_window_height.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=0, upper=2161, step_increment=1, page_increment=10, page_size=1)
        self.ms_window_height.configure(adj, 1, 0)
        self.ms_window_height.set_value(settings["height"])

        self.ms_icon_size_large = builder.get_object("icon-size-large")
        self.ms_icon_size_large.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=16, upper=129, step_increment=1, page_increment=10, page_size=1)
        self.ms_icon_size_large.configure(adj, 1, 0)
        self.ms_icon_size_large.set_value(settings["icon-size-large"])

        self.ms_icon_size_small = builder.get_object("icon-size-small")
        self.ms_icon_size_small.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=16, upper=129, step_increment=1, page_increment=10, page_size=1)
        self.ms_icon_size_small.configure(adj, 1, 0)
        self.ms_icon_size_small.set_value(settings["icon-size-small"])

        self.ms_icon_size_button = builder.get_object("icon-size-button")
        self.ms_icon_size_button.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=8, upper=129, step_increment=1, page_increment=10, page_size=1)
        self.ms_icon_size_button.configure(adj, 1, 0)
        self.ms_icon_size_button.set_value(settings["icon-size-button"])

        self.ms_padding = builder.get_object("padding")
        self.ms_padding.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=0, upper=100, step_increment=1, page_increment=10, page_size=1)
        self.ms_padding.configure(adj, 1, 0)
        self.ms_padding.set_value(settings["padding"])

        self.ms_margin_bottom = builder.get_object("margin-bottom")
        self.ms_margin_bottom.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=0, upper=400, step_increment=1, page_increment=10, page_size=1)
        self.ms_margin_bottom.configure(adj, 1, 0)
        self.ms_margin_bottom.set_value(settings["margin-bottom"])

        self.ms_margin_left = builder.get_object("margin-left")
        self.ms_margin_left.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=0, upper=400, step_increment=1, page_increment=10, page_size=1)
        self.ms_margin_left.configure(adj, 1, 0)
        self.ms_margin_left.set_value(settings["margin-left"])

        self.ms_margin_top = builder.get_object("margin-top")
        self.ms_margin_top.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=0, upper=400, step_increment=1, page_increment=10, page_size=1)
        self.ms_margin_top.configure(adj, 1, 0)
        self.ms_margin_top.set_value(settings["margin-top"])

        self.ms_margin_right = builder.get_object("margin-right")
        self.ms_margin_right.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=0, upper=400, step_increment=1, page_increment=10, page_size=1)
        self.ms_margin_right.configure(adj, 1, 0)
        self.ms_margin_right.set_value(settings["margin-right"])

        self.ms_cmd_lock = builder.get_object("cmd-lock")
        self.ms_cmd_lock.set_text(settings["cmd-lock"])

        self.ms_cmd_logout = builder.get_object("cmd-logout")
        self.ms_cmd_logout.set_text(settings["cmd-logout"])

        self.ms_cmd_restart = builder.get_object("cmd-restart")
        self.ms_cmd_restart.set_text(settings["cmd-restart"])

        self.ms_cmd_shutdown = builder.get_object("cmd-shutdown")
        self.ms_cmd_shutdown.set_text(settings["cmd-shutdown"])

        self.ms_file_manager = builder.get_object("file-manager")
        self.ms_file_manager.set_text(settings["file-manager"])

        self.ms_terminal = builder.get_object("terminal")
        self.ms_terminal.set_text(settings["terminal"])

        self.ms_autohide = builder.get_object("autohide")
        self.ms_autohide.set_active(settings["autohide"])

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(frame)

    def update_menu_start(self):
        settings = self.panel["menu-start-settings"]

        settings["width"] = int(self.ms_window_width.get_value())
        settings["height"] = int(self.ms_window_height.get_value())
        settings["icon-size-large"] = int(self.ms_icon_size_large.get_value())
        settings["icon-size-small"] = int(self.ms_icon_size_small.get_value())
        settings["icon-size-button"] = int(self.ms_icon_size_button.get_value())
        settings["padding"] = int(self.ms_padding.get_value())
        settings["margin-bottom"] = int(self.ms_margin_bottom.get_value())
        settings["margin-left"] = int(self.ms_margin_left.get_value())
        settings["margin-top"] = int(self.ms_margin_top.get_value())
        settings["margin-right"] = int(self.ms_margin_right.get_value())

        val = self.ms_cmd_lock.get_text()
        if val:
            settings["cmd-lock"] = val

        val = self.ms_cmd_logout.get_text()
        if val:
            settings["cmd-logout"] = val

        val = self.ms_cmd_restart.get_text()
        if val:
            settings["cmd-restart"] = val

        val = self.ms_cmd_shutdown.get_text()
        if val:
            settings["cmd-shutdown"] = val

        val = self.ms_file_manager.get_text()
        if val:
            settings["file-manager"] = val

        val = self.ms_terminal.get_text()
        if val:
            settings["terminal"] = val

        val = self.ms_autohide.get_active()
        if val is not None:
            settings["autohide"] = val

        save_json(self.config, self.file)

    def edit_scratchpad(self, *args):
        self.load_panel()
        self.edited = "scratchpad"
        check_key(self.panel, "scratchpad", {})
        settings = self.panel["scratchpad"]
        defaults = {
            "css-name": "",
            "icon-size": 16,
            "angle": 0.0
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_scratchpad.glade"))
        frame = builder.get_object("frame")

        self.scratchpad_css_name = builder.get_object("css-name")
        self.scratchpad_css_name.set_text(settings["css-name"])

        self.scratchpad_icon_size = builder.get_object("icon-size")
        self.scratchpad_icon_size.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=8, upper=128, step_increment=1, page_increment=10, page_size=1)
        self.scratchpad_icon_size.configure(adj, 1, 0)
        self.scratchpad_icon_size.set_value(settings["icon-size"])

        self.scratchpad_angle = builder.get_object("angle")
        self.scratchpad_angle.set_active_id(str(settings["angle"]))

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(frame)

    def update_scratchpad(self, *args):
        settings = self.panel["scratchpad"]
        settings["css-name"] = self.scratchpad_css_name.get_text()
        settings["icon-size"] = int(self.scratchpad_icon_size.get_value())

        try:
            settings["angle"] = float(self.scratchpad_angle.get_active_id())
        except:
            settings["angle"] = 0.0

        save_json(self.config, self.file)

    def edit_openweather(self, *args):
        self.load_panel()
        self.edited = "openweather"
        check_key(self.panel, "openweather", {})
        settings = self.panel["openweather"]
        defaults = {
            "module-id": str(time.time()),
            "appid": "",
            "weatherbit-api-key": "",
            "lat": None,
            "long": None,
            "lang": "en",
            "units": "metric",
            "interval": 1800,
            "loc-name": "",
            "weather-icons": "color",

            "on-right-click": "",
            "on-middle-click": "",
            "on-scroll": "",
            "icon-placement": "start",
            "icon-size": 24,
            "css-name": "weather",
            "show-name": False,
            "angle": 0.0,

            "ow-popup-icons": "light",
            "popup-header-icon-size": 48,
            "popup-icon-size": 24,
            "popup-text-size": "medium",
            "popup-css-name": "weather-forecast",
            "popup-placement": "right",
            "popup-margin-horizontal": 0,
            "popup-margin-top": 0,
            "popup-margin-bottom": 0,
            "show-humidity": True,
            "show-wind": True,
            "show-pressure": True,
            "show-cloudiness": True,
            "show-visibility": True,
            "show-pop": True,
            "show-volume":True
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_openweather.glade"))
        frame = builder.get_object("frame")

        self.ow_appid = builder.get_object("appid")
        self.ow_appid.set_text(settings["appid"])
        self.ow_appid.connect("changed", self.mark_weather_data_delete)

        key_visibility_switch = builder.get_object("key-visibility-switch")
        key_visibility_switch.connect("toggled", switch_entry_visibility, self.ow_appid)

        self.weatherbit_api_key = builder.get_object("weatherbit-api-key")
        self.weatherbit_api_key.set_text(settings["weatherbit-api-key"])

        key_visibility_switch1 = builder.get_object("key-visibility-switch1")
        key_visibility_switch1.connect("toggled", switch_entry_visibility, self.weatherbit_api_key)

        # Try to obtain geolocation if unset
        if not settings["lat"] or not settings["long"]:
            # Try nwg-shell settings
            shell_settings_file = os.path.join(data_home, "nwg-shell-config", "settings")
            if os.path.isfile(shell_settings_file):
                shell_settings = load_json(shell_settings_file)
                eprint("OpenWeather: coordinates not set, loading from nwg-shell settings")
                settings["lat"] = shell_settings["night-lat"]
                settings["long"] = shell_settings["night-long"]
                eprint("lat = {}, long = {}".format(settings["lat"], settings["long"]))
            else:
                # Set dummy location
                eprint("OpenWeather: coordinates not set, setting Big Ben in London 51.5008, -0.1246")
                settings["lat"] = 51.5008
                settings["long"] = -0.1246

        self.ow_lat = builder.get_object("lat")
        adj = Gtk.Adjustment(value=0, lower=-90, upper=90, step_increment=0.1, page_increment=10, page_size=1)
        self.ow_lat.configure(adj, 1, 4)
        self.ow_lat.set_value(settings["lat"])
        self.ow_lat.connect("value-changed", self.mark_weather_data_delete)

        self.ow_long = builder.get_object("long")
        adj = Gtk.Adjustment(value=0, lower=-180, upper=180, step_increment=0.1, page_increment=10, page_size=1)
        self.ow_long.configure(adj, 1, 4)
        self.ow_long.set_value(settings["long"])
        self.ow_long.connect("value-changed", self.mark_weather_data_delete)

        self.ow_lang = builder.get_object("lang")
        self.ow_lang.set_text(settings["lang"])
        self.ow_lang.connect("changed", self.mark_weather_data_delete)

        self.ow_units = builder.get_object("units")
        self.ow_units.set_active_id(settings["units"])
        self.ow_units.connect("changed", self.mark_weather_data_delete)

        self.ow_interval = builder.get_object("interval")
        adj = Gtk.Adjustment(value=0, lower=180, upper=86401, step_increment=1, page_increment=10, page_size=1)
        self.ow_interval.configure(adj, 1, 0)
        self.ow_interval.set_value(settings["interval"])

        self.ow_weather_icons = builder.get_object("weather-icons")
        self.ow_weather_icons.set_active_id(settings["weather-icons"])

        self.ow_loc_name = builder.get_object("loc-name")
        self.ow_loc_name.set_text(settings["loc-name"])

        self.ow_on_right_click = builder.get_object("on-right-click")
        self.ow_on_right_click.set_text(settings["on-right-click"])

        self.ow_on_middle_click = builder.get_object("on-middle-click")
        self.ow_on_middle_click.set_text(settings["on-middle-click"])

        self.ow_on_scroll = builder.get_object("on-scroll")
        self.ow_on_scroll.set_text(settings["on-scroll"])

        self.ow_icon_placement = builder.get_object("icon-placement")
        self.ow_icon_placement.set_active_id(settings["icon-placement"])

        self.ow_icon_size = builder.get_object("icon-size")
        adj = Gtk.Adjustment(value=0, lower=8, upper=129, step_increment=1, page_increment=10, page_size=1)
        self.ow_icon_size.configure(adj, 1, 0)
        self.ow_icon_size.set_value(settings["icon-size"])

        self.ow_css_name = builder.get_object("css-name")
        self.ow_css_name.set_text(settings["css-name"])

        self.ow_angle = builder.get_object("angle")
        self.ow_angle.set_active_id(str(settings["angle"]))

        self.ow_show_name = builder.get_object("show-name")
        self.ow_show_name.set_active(settings["show-name"])

        self.ow_popup_icons = builder.get_object("ow-popup-icons")
        self.ow_popup_icons.set_active_id(settings["ow-popup-icons"])

        self.ow_popup_header_icon_size = builder.get_object("popup-header-icon-size")
        adj = Gtk.Adjustment(value=0, lower=8, upper=129, step_increment=1, page_increment=10, page_size=1)
        self.ow_popup_header_icon_size.configure(adj, 1, 0)
        self.ow_popup_header_icon_size.set_value(settings["popup-header-icon-size"])

        self.ow_popup_icon_size = builder.get_object("popup-icon-size")
        adj = Gtk.Adjustment(value=0, lower=8, upper=49, step_increment=1, page_increment=10, page_size=1)
        self.ow_popup_icon_size.configure(adj, 1, 0)
        self.ow_popup_icon_size.set_value(settings["popup-icon-size"])

        self.ow_popup_text_size = builder.get_object("popup-text-size")
        self.ow_popup_text_size.set_active_id(settings["popup-text-size"])

        self.ow_popup_css_name = builder.get_object("popup-css-name")
        self.ow_popup_css_name.set_text(settings["popup-css-name"])

        self.ow_popup_placement = builder.get_object("popup-placement")
        self.ow_popup_placement.set_active_id(settings["popup-placement"])

        self.ow_popup_margin_horizontal = builder.get_object("popup-margin-horizontal")
        adj = Gtk.Adjustment(value=0, lower=0, upper=3000, step_increment=1, page_increment=10, page_size=1)
        self.ow_popup_margin_horizontal.configure(adj, 1, 0)
        self.ow_popup_margin_horizontal.set_value(settings["popup-margin-horizontal"])

        self.ow_popup_margin_top = builder.get_object("popup-margin-top")
        adj = Gtk.Adjustment(value=0, lower=0, upper=2000, step_increment=1, page_increment=10, page_size=1)
        self.ow_popup_margin_top.configure(adj, 1, 0)
        self.ow_popup_margin_top.set_value(settings["popup-margin-top"])

        self.ow_popup_margin_bottom = builder.get_object("popup-margin-bottom")
        adj = Gtk.Adjustment(value=0, lower=0, upper=2000, step_increment=1, page_increment=10, page_size=1)
        self.ow_popup_margin_bottom.configure(adj, 1, 0)
        self.ow_popup_margin_bottom.set_value(settings["popup-margin-bottom"])

        self.ow_show_humidity = builder.get_object("show-humidity")
        self.ow_show_humidity.set_active(settings["show-humidity"])

        self.ow_show_wind = builder.get_object("show-wind")
        self.ow_show_wind.set_active(settings["show-wind"])

        self.ow_show_pressure = builder.get_object("show-pressure")
        self.ow_show_pressure.set_active(settings["show-pressure"])

        self.ow_show_cloudiness = builder.get_object("show-cloudiness")
        self.ow_show_cloudiness.set_active(settings["show-cloudiness"])

        self.ow_show_visibility = builder.get_object("show-visibility")
        self.ow_show_visibility.set_active(settings["show-visibility"])

        self.ow_show_pop = builder.get_object("show-pop")
        self.ow_show_pop.set_active(settings["show-pop"])

        self.ow_show_volume = builder.get_object("show-volume")
        self.ow_show_volume.set_active(settings["show-volume"])

        self.ow_module_id = builder.get_object("module-id")
        self.ow_module_id.set_text(settings["module-id"])

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(frame)

    def mark_weather_data_delete(self, *args):
        eprint("Weather data files marked for deletion")
        self.delete_weather_data = True

    def update_openweather(self, *args):
        settings = self.panel["openweather"]

        settings["appid"] = self.ow_appid.get_text()
        settings["weatherbit-api-key"] = self.weatherbit_api_key.get_text()
        settings["lat"] = round(self.ow_lat.get_value(), 4)
        settings["long"] = round(self.ow_long.get_value(), 4)
        settings["lang"] = self.ow_lang.get_text()
        settings["units"] = self.ow_units.get_active_id()
        settings["interval"] = int(self.ow_interval.get_value())
        settings["loc-name"] = self.ow_loc_name.get_text()
        settings["weather-icons"] = self.ow_weather_icons.get_active_id()
        settings["on-right-click"] = self.ow_on_right_click.get_text()
        settings["on-middle-click"] = self.ow_on_middle_click.get_text()
        settings["on-scroll"] = self.ow_on_scroll.get_text()
        settings["icon-placement"] = self.ow_icon_placement.get_active_id()
        settings["icon-size"] = int(self.ow_icon_size.get_value())
        settings["css-name"] = self.ow_css_name.get_text()
        settings["show-name"] = self.ow_show_name.get_active()
        try:
            settings["angle"] = float(self.ow_angle.get_active_id())
        except:
            settings["angle"] = 0.0
        settings["ow-popup-icons"] = self.ow_popup_icons.get_active_id()
        settings["popup-header-icon-size"] = int(self.ow_popup_header_icon_size.get_value())
        settings["popup-icon-size"] = int(self.ow_popup_icon_size.get_value())
        settings["popup-text-size"] = self.ow_popup_text_size.get_active_id()
        settings["popup-css-name"] = self.ow_popup_css_name.get_text()
        settings["popup-placement"] = self.ow_popup_placement.get_active_id()
        settings["popup-margin-horizontal"] = int(self.ow_popup_margin_horizontal.get_value())
        settings["popup-margin-top"] = int(self.ow_popup_margin_top.get_value())
        settings["popup-margin-bottom"] = int(self.ow_popup_margin_bottom.get_value())
        settings["show-humidity"] = self.ow_show_humidity.get_active()
        settings["show-wind"] = self.ow_show_wind.get_active()
        settings["show-pressure"] = self.ow_show_pressure.get_active()
        settings["show-cloudiness"] = self.ow_show_cloudiness.get_active()
        settings["show-visibility"] = self.ow_show_visibility.get_active()
        settings["show-pop"] = self.ow_show_pop.get_active()
        settings["show-volume"] = self.ow_show_volume.get_active()

        save_json(self.config, self.file)
    
    def edit_brightness_slider(self, *args):
        self.load_panel()
        self.edited = "brightness-slider"
        check_key(self.panel, "brightness-slider", {})
        settings = self.panel["brightness-slider"]

        defaults = {
            "show-values": True,
            "icon-size": 16,
            "interval": 10,
            "hover-opens": False,
            "leave-closes": False,
            "root-css-name": "brightness-module",
            "css-name": "brightness-popup",
            "angle": 0.0,
            "icon-placement": "start",
            "backlight-device": "",
            "backlight-controller": "light",
            "slider-orientation": "horizontal",
            "slider-inverted": False,
            "popup-icon-placement": "start",
            "popup-horizontal-alignment": "left",
            "popup-vertical-alignment": "top",
            "popup-width": 256,
            "popup-height": 64,
            "popup-horizontal-margin": 0,
            "popup-vertical-margin": 0,
            "step-size": 1,
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_brightness_slider.glade"))
        frame = builder.get_object("frame")

        self.brightness_slider_config = {}
        for setting in defaults:
            widget = builder.get_object(setting)
            value = settings[setting]

            if type(widget) == Gtk.Entry:
                widget.set_text(value.strip())
            elif type(widget) == Gtk.SpinButton:
                widget.set_numeric(True)
                adj = Gtk.Adjustment(value=0, lower=0, upper=10000, step_increment=1, page_increment=10, page_size=1)
                widget.configure(adj, 1, 0)
                widget.set_value(value)
            elif type(widget) == Gtk.CheckButton:
                widget.set_active(value)
            elif type(widget) in [Gtk.ComboBoxText, Gtk.ComboBox]:
                widget.set_active_id(str(value))
            self.brightness_slider_config[setting] = widget
        
        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(frame)

    def update_brightness_slider(self):
        settings = self.panel["brightness-slider"]
        
        for setting, widget in self.brightness_slider_config.items():
            if type(widget) == Gtk.Entry:
                value = widget.get_text()
            elif type(widget) == Gtk.SpinButton:
                value = int(widget.get_value())
            elif type(widget) == Gtk.CheckButton:
                value = widget.get_active()
            elif type(widget) in [Gtk.ComboBoxText, Gtk.ComboBox]:
                value = widget.get_active_id()
                if setting == "angle":
                    value = float(value)
            settings[setting] = value
        save_json(self.config, self.file)

    def edit_dwl_tags(self, *args):
        self.load_panel()
        self.edited = "dwl-tags"
        check_key(self.panel, "dwl-tags", {})
        settings = self.panel["dwl-tags"]
        defaults = {
            "tag-names": "1 2 3 4 5 6 7 8 9",
            "title-limit": 55,
            "angle": 0.0
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_dwl_tags.glade"))
        frame = builder.get_object("frame")

        self.dwl_tag_names = builder.get_object("tag-names")
        self.dwl_tag_names.set_text(settings["tag-names"])

        self.dwl_tags_title_limit = builder.get_object("title-limit")
        self.dwl_tags_title_limit.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=1, upper=256, step_increment=1, page_increment=10, page_size=1)
        self.dwl_tags_title_limit.configure(adj, 1, 0)
        self.dwl_tags_title_limit.set_value(settings["title-limit"])

        self.dwl_angle = builder.get_object("angle")
        self.dwl_angle.set_active_id(str(settings["angle"]))

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(frame)

    def update_dwl_tags(self, *args):
        settings = self.panel["dwl-tags"]
        settings["tag-names"] = self.dwl_tag_names.get_text()
        settings["title-limit"] = int(self.dwl_tags_title_limit.get_value())

        try:
            settings["angle"] = float(self.dwl_angle.get_active_id())
        except:
            settings["angle"] = 0.0

        save_json(self.config, self.file)

    def select_executor(self, ebox, event):
        self.edited = "executors"
        menu = Gtk.Menu()
        executors = []  # Why the list? We need the number of executors.
        for key in self.panel:
            if key.startswith("executor-"):
                executors.append(key)
        for name in executors:
            item = Gtk.MenuItem.new_with_label(name[9:])
            item.connect("activate", self.edit_executor, name)
            menu.append(item)

        item = Gtk.SeparatorMenuItem()
        menu.append(item)
        item = Gtk.MenuItem.new_with_label("Add new")
        menu.append(item)
        item.connect("activate", self.edit_executor, "executor-unnamed_{}".format(len(executors) + 1), True)
        if self.executors_base:
            item = Gtk.MenuItem.new_with_label("Database")
            item.connect("activate", self.import_executor)
            menu.append(item)

        menu.show_all()
        menu.popup_at_widget(ebox.get_parent(), Gdk.Gravity.EAST, Gdk.Gravity.WEST, None)

    def edit_executor(self, item, name, new=False):
        self.load_panel()
        self.edited = "executor"
        settings = self.panel[name] if not new else {}
        defaults = {
            "script": "",
            "tooltip-text": "",
            "on-left-click": "",
            "on-middle-click": "",
            "on-right-click": "",
            "on-scroll-up": "",
            "on-scroll-down": "",
            "root-css-name": "",
            "css-name": "",
            "icon-placement": "left",
            "icon-size": 16,
            "interval": 1,
            "angle": 0.0
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_executor.glade"))
        frame = builder.get_object("frame")

        self.executor_name = builder.get_object("name")
        self.executor_name.set_text(name[9:])
        self.executor_name.connect("changed", validate_name)

        self.executor_script = builder.get_object("script")
        self.executor_script.set_text(settings["script"])

        self.executor_tooltip_text = builder.get_object("tooltip-text")
        self.executor_tooltip_text.set_text(settings["tooltip-text"])

        self.executor_on_left_click = builder.get_object("on-left-click")
        self.executor_on_left_click.set_text(settings["on-left-click"])

        self.executor_on_middle_click = builder.get_object("on-middle-click")
        self.executor_on_middle_click.set_text(settings["on-middle-click"])

        self.executor_on_right_click = builder.get_object("on-right-click")
        self.executor_on_right_click.set_text(settings["on-right-click"])

        self.executor_on_scroll_up = builder.get_object("on-scroll-up")
        self.executor_on_scroll_up.set_text(settings["on-scroll-up"])

        self.executor_on_scroll_down = builder.get_object("on-scroll-down")
        self.executor_on_scroll_down.set_text(settings["on-scroll-down"])

        self.executor_root_css_name = builder.get_object("root-css-name")
        self.executor_root_css_name.set_text(settings["root-css-name"])

        self.executor_css_name = builder.get_object("css-name")
        self.executor_css_name.set_text(settings["css-name"])

        self.executor_icon_placement = builder.get_object("icon-placement")
        self.executor_icon_placement.set_active_id(settings["icon-placement"])

        self.executor_icon_size = builder.get_object("icon-size")
        self.executor_icon_size.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=8, upper=128, step_increment=1, page_increment=10, page_size=1)
        self.executor_icon_size.configure(adj, 1, 0)
        self.executor_icon_size.set_value(settings["icon-size"])

        self.executor_interval = builder.get_object("interval")
        self.executor_interval.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=1, upper=3600, step_increment=1, page_increment=10, page_size=1)
        self.executor_interval.configure(adj, 1, 0)
        self.executor_interval.set_value(settings["interval"])

        self.executor_angle = builder.get_object("angle")
        self.executor_angle.set_active_id(str(settings["angle"]))

        self.executor_remove = builder.get_object("remove")

        self.executor_save_to_db_btn = builder.get_object("save-to-database")
        self.executor_save_to_db_btn.connect("clicked", self.check_and_save_to_db, name, settings)
        if new:
            self.executor_remove.set_visible(False)
            self.executor_save_to_db_btn.set_visible(False)

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(frame)

    def check_and_save_to_db(self, btn, name, settings):
        if name not in self.executors_base:
            self.save_executor_to_db(btn, name, settings)
        else:
            menu = Gtk.Menu()
            item = Gtk.MenuItem.new_with_label("Replace '{}' in database".format(name))
            item.connect("activate", self.save_executor_to_db, name, settings)
            menu.append(item)
            menu.set_reserve_toggle_size(False)
            menu.show_all()
            menu.popup_at_widget(btn, Gdk.Gravity.NORTH, Gdk.Gravity.SOUTH, None)

    def save_executor_to_db(self, widget, name, settings):
        self.executors_base[name] = settings
        save_json(self.executors_base, self.executors_file)

    def update_executor(self):
        config_key = "executor-{}".format(self.executor_name.get_text())
        settings = self.panel[config_key] if config_key in self.panel else {}

        if not self.executor_remove.get_active():
            settings["script"] = self.executor_script.get_text()
            settings["tooltip-text"] = self.executor_tooltip_text.get_text()
            settings["on-left-click"] = self.executor_on_left_click.get_text()
            settings["on-middle-click"] = self.executor_on_middle_click.get_text()
            settings["on-right-click"] = self.executor_on_right_click.get_text()
            settings["on-scroll-up"] = self.executor_on_scroll_up.get_text()
            settings["on-scroll-down"] = self.executor_on_scroll_down.get_text()
            settings["root-css-name"] = self.executor_root_css_name.get_text()
            settings["css-name"] = self.executor_css_name.get_text()
            val = self.executor_icon_placement.get_active_id()
            if val:
                settings["icon-placement"] = val
            settings["icon-size"] = int(self.executor_icon_size.get_value())
            settings["interval"] = int(self.executor_interval.get_value())

            try:
                settings["angle"] = float(self.executor_angle.get_active_id())
            except:
                settings["angle"] = 0.0

            self.panel[config_key] = settings
        else:
            # delete from panel
            try:
                self.panel.pop(config_key)
                print("Removed '{}' from panel".format(config_key))
            except:
                pass

            # delete from modules left/center/right if exists
            try:
                for item in self.panel["modules-left"]:
                    if item == config_key:
                        self.panel["modules-left"].remove(item)
                        print("Removed '{}' from modules-left".format(config_key))
            except:
                pass

            try:
                for item in self.panel["modules-center"]:
                    if item == config_key:
                        self.panel["modules-center"].remove(item)
                        print("Removed '{}' from modules-center".format(config_key))
            except:
                pass

            try:
                for item in self.panel["modules-right"]:
                    if item == config_key:
                        self.panel["modules-right"].remove(item)
                        print("Removed '{}' from modules-right".format(config_key))
            except:
                pass

        save_json(self.config, self.file)

    def import_executor(self, item):
        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/executor_import.glade"))
        frame = builder.get_object("frame")

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(frame)

        self.ie_combo = builder.get_object("select")
        for key in self.executors_base:
            self.ie_combo.append(key, key)
        self.ie_combo.connect("changed", self.ie_on_combo_changed, self.executors_base)

        self.ie_script = builder.get_object("script")
        self.ie_interval = builder.get_object("interval")
        self.ie_icon_size = builder.get_object("icon-size")
        self.ie_on_left_click = builder.get_object("on-left-click")
        self.ie_on_middle_click = builder.get_object("on-middle-click")
        self.ie_on_right_click = builder.get_object("on-right-click")
        self.ie_on_scroll_up = builder.get_object("on-scroll-up")
        self.ie_on_scroll_down = builder.get_object("on-scroll-down")
        self.ie_tooltip_text = builder.get_object("tooltip-text")
        self.ie_icon_placement = builder.get_object("icon-placement")
        self.ie_css_name = builder.get_object("css-name")

        self.ie_btn_delete = builder.get_object("btn-delete")
        self.ie_btn_delete.connect("clicked", self.ie_show_btn_delete_menu)
        self.ie_btn_import = builder.get_object("btn-import")
        self.ie_btn_import.set_label("Add to '{}'".format(self.panel["name"]))
        self.ie_btn_import.connect("clicked", self.ie_on_import_btn)

    def ie_on_import_btn(self, btn):
        executor = self.ie_combo.get_active_text()
        if executor not in self.panel:
            self.ie_add_executor(btn, executor)
        else:
            self.ie_show_btn_import_menu(btn)

    def ie_show_btn_import_menu(self, btn):
        executor = self.ie_combo.get_active_text()
        menu = Gtk.Menu()
        item = Gtk.MenuItem.new_with_label("Replace '{}' in '{}'".format(executor, self.panel["name"]))
        item.connect("activate", self.ie_add_executor, executor)
        menu.append(item)
        menu.set_reserve_toggle_size(False)
        menu.show_all()
        menu.popup_at_widget(btn, Gdk.Gravity.NORTH, Gdk.Gravity.SOUTH, None)

    def ie_show_btn_delete_menu(self, btn):
        executor = self.ie_combo.get_active_text()
        menu = Gtk.Menu()
        item = Gtk.MenuItem.new_with_label("Delete '{}' from database".format(executor))
        item.connect("activate", self.ie_remove_executor, executor)
        menu.append(item)
        menu.set_reserve_toggle_size(False)
        menu.show_all()
        menu.popup_at_widget(btn, Gdk.Gravity.NORTH, Gdk.Gravity.SOUTH, None)

    def ie_add_executor(self, widget, executor):
        self.panel[executor] = self.executors_base[executor].copy()
        save_json(self.config, self.file)

    def ie_remove_executor(self, item, executor):
        del self.executors_base[executor]
        self.ie_combo.remove_all()
        for key in self.executors_base:
            self.ie_combo.append(key, key)
        for label in [self.ie_script, self.ie_interval, self.ie_icon_size, self.ie_on_left_click,
                      self.ie_on_middle_click, self.ie_on_right_click, self.ie_on_scroll_up, self.ie_on_scroll_down,
                      self.ie_tooltip_text, self.ie_icon_placement, self.ie_css_name]:
            label.set_text("")
        save_json(self.executors_base, self.executors_file)

    def ie_on_combo_changed(self, combo, executors):
        executor = combo.get_active_text()
        if executor:
            self.ie_script.set_text(executors[executor]["script"])
            self.ie_interval.set_text(str(executors[executor]["interval"]))
            self.ie_icon_size.set_text(str(executors[executor]["icon-size"]))
            self.ie_on_left_click.set_text(executors[executor]["on-left-click"])
            self.ie_on_middle_click.set_text(executors[executor]["on-middle-click"])
            self.ie_on_right_click.set_text(executors[executor]["on-right-click"])
            self.ie_on_scroll_up.set_text(executors[executor]["on-scroll-up"])
            self.ie_on_scroll_down.set_text(executors[executor]["on-scroll-down"])
            self.ie_tooltip_text.set_text(executors[executor]["tooltip-text"])
            self.ie_icon_placement.set_text(executors[executor]["icon-placement"])
            self.ie_css_name.set_text(executors[executor]["css-name"])

            self.ie_btn_delete.set_sensitive(True)
            self.ie_btn_import.set_sensitive(True)

    def select_button(self, ebox, event):
        self.edited = "buttons"
        menu = Gtk.Menu()
        buttons = []
        for key in self.panel:
            if key.startswith("button-"):
                buttons.append(key)
        for name in buttons:
            item = Gtk.MenuItem.new_with_label(name[7:])
            item.connect("activate", self.edit_button, name)
            menu.append(item)

        item = Gtk.SeparatorMenuItem()
        menu.append(item)
        item = Gtk.MenuItem.new_with_label("Add new")
        menu.append(item)
        item.connect("activate", self.edit_button, "button-unnamed_{}".format(len(buttons) + 1),
                     True)
        menu.show_all()
        menu.popup_at_widget(ebox.get_parent(), Gdk.Gravity.EAST, Gdk.Gravity.WEST, None)

    def edit_button(self, item, name, new=False):
        self.load_panel()
        self.edited = "button"
        settings = self.panel[name] if not new else {}
        defaults = {
            "command": "",
            "icon": "",
            "label": "",
            "tooltip": "",
            "label-position": "right",
            "css-name": "",
            "icon-size": 16
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_button.glade"))
        frame = builder.get_object("frame")

        self.button_name = builder.get_object("name")
        self.button_name.set_text(name[7:])
        self.button_name.connect("changed", validate_name)

        self.button_command = builder.get_object("command")
        self.button_command.set_text(settings["command"])

        self.button_icon = builder.get_object("icon")
        self.button_icon.set_text(settings["icon"])
        update_icon(self.button_icon, self.panel["icons"])
        self.button_icon.connect("changed", update_icon, self.panel["icons"])

        self.button_picker = builder.get_object("btn-picker")
        img = Gtk.Image.new_from_icon_name("nwg-icon-picker", Gtk.IconSize.BUTTON)
        self.button_picker.set_image(img)

        if is_command("nwg-icon-picker"):
            self.button_picker.set_tooltip_text("Pick an icon")
            self.button_picker.connect("clicked", on_pick_btn, self.button_icon)
        else:
            self.button_picker.hide()

        self.button_label = builder.get_object("label")
        self.button_label.set_text(settings["label"])

        self.button_label_position = builder.get_object("label-position")
        self.button_label_position.set_active_id(settings["label-position"])

        self.button_tooltip = builder.get_object("tooltip")
        self.button_tooltip.set_text(settings["tooltip"])

        self.button_css_name = builder.get_object("css-name")
        self.button_css_name.set_text(settings["css-name"])

        self.button_icon_size = builder.get_object("icon-size")
        self.button_icon_size.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=8, upper=128, step_increment=1, page_increment=10, page_size=1)
        self.button_icon_size.configure(adj, 1, 0)
        self.button_icon_size.set_value(settings["icon-size"])

        self.button_remove = builder.get_object("remove")
        self.button_remove.set_sensitive(name in self.panel)

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(frame)

    def update_button(self):
        config_key = "button-{}".format(self.button_name.get_text())
        settings = self.panel[config_key] if config_key in self.panel else {}

        if not self.button_remove.get_active():
            settings["command"] = self.button_command.get_text()
            settings["icon"] = self.button_icon.get_text()
            settings["label"] = self.button_label.get_text()
            settings["label-position"] = self.button_label_position.get_active_id()
            settings["tooltip"] = self.button_tooltip.get_text()
            settings["css-name"] = self.button_css_name.get_text()
            settings["icon-size"] = int(self.button_icon_size.get_value())

            self.panel[config_key] = settings
        else:
            # delete from panel
            try:
                self.panel.pop(config_key)
                print("Removed '{}' from panel".format(config_key))
            except:
                pass

            # delete from modules left/center/right if exists
            try:
                for item in self.panel["modules-left"]:
                    if item == config_key:
                        self.panel["modules-left"].remove(item)
                        print("Removed '{}' from modules-left".format(config_key))
            except:
                pass

            try:
                for item in self.panel["modules-center"]:
                    if item == config_key:
                        self.panel["modules-center"].remove(item)
                        print("Removed '{}' from modules-center".format(config_key))
            except:
                pass

            try:
                for item in self.panel["modules-right"]:
                    if item == config_key:
                        self.panel["modules-right"].remove(item)
                        print("Removed '{}' from modules-right".format(config_key))
            except:
                pass

        save_json(self.config, self.file)

    def edit_modules(self, ebox, event, which):
        self.load_panel()

        self.edited = "modules"
        self.modules = None
        if which == "left":
            check_key(self.panel, "modules-left", [])
            self.modules = self.panel["modules-left"]
        elif which == "center":
            check_key(self.panel, "modules-center", [])
            self.modules = self.panel["modules-center"]
        elif which == "right":
            check_key(self.panel, "modules-right", [])
            self.modules = self.panel["modules-right"]

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_modules.glade"))
        modules_label = builder.get_object("label")
        modules_label.set_text("{} {}".format(modules_label.get_text(), which.capitalize()))
        frame = builder.get_object("frame")
        self.modules_grid = builder.get_object("grid")
        self.modules_combo = builder.get_object("menu")

        btn = builder.get_object("btn-append")
        btn.connect("clicked", self.append)

        # Built-in stuff first
        for key in self.panel:
            if key in self.known_modules:
                self.modules_combo.append(key, key.capitalize())

        for key in self.panel:
            if key.startswith("executor-") or key.startswith("button-"):
                self.modules_combo.append(key, key)

        self.modules_combo.set_active(0)
        self.modules_combo.show_all()

        self.refresh_listbox()

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(frame)

    def refresh_listbox(self):
        if self.modules_grid.get_child_at(1, 2) is not None:
            self.modules_grid.get_child_at(1, 2).destroy()

        self.modules_listbox = self.build_listbox()
        self.modules_grid.attach(self.modules_listbox, 1, 2, 2, 1)

    def build_listbox(self):
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        for i in range(len(self.modules)):
            module = self.modules[i]
            if module in self.panel:
                row = Gtk.ListBoxRow()
                vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                row.add(vbox)
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                vbox.pack_start(hbox, False, False, 6)

                label = Gtk.Label()
                label.set_text(module)
                label.set_xalign(0)
                Gtk.Widget.set_size_request(label, 180, 1)
                hbox.pack_start(label, False, False, 6)

                btn = Gtk.Button.new_from_icon_name("go-up", Gtk.IconSize.MENU)
                btn.set_always_show_image(True)
                btn.set_sensitive(i > 0)
                btn.connect("clicked", self.move_up, module)
                hbox.pack_start(btn, False, False, 0)

                btn = Gtk.Button.new_from_icon_name("go-down", Gtk.IconSize.MENU)
                btn.set_always_show_image(True)
                btn.set_sensitive(i < len(self.modules) - 1)
                btn.connect("clicked", self.move_down, module)
                hbox.pack_start(btn, False, False, 0)

                btn = Gtk.Button.new_from_icon_name("list-remove", Gtk.IconSize.MENU)
                btn.set_always_show_image(True)
                btn.connect("clicked", self.delete, module)
                hbox.pack_start(btn, False, False, 0)

                listbox.add(row)
        listbox.show_all()

        return listbox

    def move_up(self, btn, module):
        old_index = self.modules.index(module)
        self.modules.insert(old_index - 1, self.modules.pop(old_index))
        self.refresh_listbox()

    def move_down(self, btn, module):
        old_index = self.modules.index(module)
        self.modules.insert(old_index + 1, self.modules.pop(old_index))
        self.refresh_listbox()

    def delete(self, btn, module):
        self.modules.remove(module)
        self.refresh_listbox()

    def append(self, btn):
        if self.modules_combo.get_active_id():
            self.modules.append(self.modules_combo.get_active_id())
            self.refresh_listbox()

    def controls_menu(self, ebox, event):
        menu = Gtk.Menu()
        item = Gtk.MenuItem.new_with_label("Settings")
        item.connect("activate", self.edit_controls)
        menu.append(item)

        item = Gtk.MenuItem.new_with_label("Custom items")
        item.connect("activate", self.edit_custom_items)
        menu.append(item)

        item = Gtk.MenuItem.new_with_label("User menu")
        item.connect("activate", self.edit_user_menu)
        menu.append(item)

        menu.show_all()
        menu.popup_at_widget(ebox.get_parent(), Gdk.Gravity.EAST, Gdk.Gravity.WEST, None)

    def edit_controls(self, *args):
        self.load_panel()
        self.edited = "controls"
        check_key(self.panel, "controls-settings", {})
        settings = self.panel["controls-settings"]
        defaults = {
            "components": [
                "net",
                "brightness",
                "volume",
                "battery"
            ],
            "commands": {
            },
            "show-values": False,
            "output-switcher": False,
            "backlight-controller": "light",
            "backlight-device": "",
            "interval": 1,
            "window-width": 0,
            "window-margin-horizontal": 0,
            "window-margin-vertical": 0,
            "icon-size": 16,
            "hover-opens": True,
            "leave-closes": True,
            "root-css-name": "controls-overview",
            "css-name": "controls-window",
            "net-interface": "",
            "angle": 0.0,
            "custom-items": [
                {
                    "name": "Panel settings",
                    "icon": "nwg-panel",
                    "cmd": "nwg-panel-config"
                }
            ],
            "menu": {
                "name": "Exit",
                "icon": "system-shutdown-symbolic",
                "items": [
                    {
                        "name": "Lock",
                        "cmd": "swaylock -f -c 000000"
                    },
                    {
                        "name": "Logout",
                        "cmd": "swaymsg exit"
                    },
                    {
                        "name": "Reboot",
                        "cmd": "systemctl reboot"
                    },
                    {
                        "name": "Shutdown",
                        "cmd": "systemctl -i poweroff"
                    }
                ]
            }
        }
        for key in defaults:
            check_key(settings, key, defaults[key])

        builder = Gtk.Builder.new_from_file(os.path.join(dir_name, "glade/config_controls.glade"))
        frame = builder.get_object("frame")

        self.ctrl_comp_brightness = builder.get_object("ctrl-comp-brightness")
        self.ctrl_comp_brightness.set_active("brightness" in settings["components"])

        self.ctrl_backlight_controller = builder.get_object("backlight-controller")
        self.ctrl_backlight_controller.set_active_id(settings["backlight-controller"])

        self.ctrl_backlight_device = builder.get_object("backlight-device")
        self.ctrl_backlight_device.set_text(settings["backlight-device"])

        self.ctrl_comp_volume = builder.get_object("ctrl-comp-volume")
        self.ctrl_comp_volume.set_active("volume" in settings["components"])

        self.ctrl_comp_switcher = builder.get_object("output-switcher")
        self.ctrl_comp_switcher.set_sensitive(is_command("pamixer"))
        self.ctrl_comp_switcher.set_active(settings["output-switcher"])

        self.ctrl_comp_net = builder.get_object("ctrl-comp-net")
        self.ctrl_comp_net.set_active("net" in settings["components"])

        self.ctrl_comp_bluetooth = builder.get_object("ctrl-comp-bluetooth")
        if is_command("btmgmt"):
            self.ctrl_comp_bluetooth.set_active("bluetooth" in settings["components"])
        else:
            self.ctrl_comp_bluetooth.set_active(False)
            self.ctrl_comp_bluetooth.set_sensitive(False)

        self.ctrl_comp_battery = builder.get_object("ctrl-comp-battery")
        self.ctrl_comp_battery.set_active("battery" in settings["components"])

        self.ctrl_cdm_net = builder.get_object("ctrl-cmd-net")
        check_key(settings["commands"], "net", "")
        self.ctrl_cdm_net.set_text(settings["commands"]["net"])

        self.ctrl_net_name = builder.get_object("ctrl-net-name")
        self.ctrl_net_name.set_text(settings["net-interface"])

        self.ctrl_cdm_bluetooth = builder.get_object("ctrl-cmd-bluetooth")
        check_key(settings["commands"], "bluetooth", "")
        self.ctrl_cdm_bluetooth.set_text(settings["commands"]["bluetooth"])

        self.ctrl_cdm_battery = builder.get_object("ctrl-cmd-battery")
        check_key(settings["commands"], "battery", "")
        self.ctrl_cdm_battery.set_text(settings["commands"]["battery"])

        self.ctrl_root_css_name = builder.get_object("root-css-name")
        self.ctrl_root_css_name.set_text(settings["root-css-name"])

        self.ctrl_css_name = builder.get_object("css-name")
        self.ctrl_css_name.set_text(settings["css-name"])

        self.ctrl_window_width = builder.get_object("window-width")
        self.ctrl_window_width.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=0, upper=1920, step_increment=1, page_increment=10, page_size=1)
        self.ctrl_window_width.configure(adj, 1, 0)
        self.ctrl_window_width.set_value(settings["window-width"])

        self.ctrl_window_margin_horizontal = builder.get_object("window-margin-horizontal")
        self.ctrl_window_margin_horizontal.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=-1920, upper=1920, step_increment=1, page_increment=10, page_size=1)
        self.ctrl_window_margin_horizontal.configure(adj, 1, 0)
        self.ctrl_window_margin_horizontal.set_value(settings["window-margin-horizontal"])

        self.ctrl_window_margin_vertical = builder.get_object("window-margin-vertical")
        self.ctrl_window_margin_vertical.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=-1920, upper=1920, step_increment=1, page_increment=10, page_size=1)
        self.ctrl_window_margin_vertical.configure(adj, 1, 0)
        self.ctrl_window_margin_vertical.set_value(settings["window-margin-vertical"])

        self.ctrl_icon_size = builder.get_object("icon-size")
        self.ctrl_icon_size.set_numeric(True)
        adj = Gtk.Adjustment(value=0, lower=8, upper=128, step_increment=1, page_increment=10, page_size=1)
        self.ctrl_icon_size.configure(adj, 1, 0)
        self.ctrl_icon_size.set_value(settings["icon-size"])

        self.ctrl_interval = builder.get_object("interval")
        self.ctrl_interval.set_numeric(True)
        adj = Gtk.Adjustment(value=1, lower=1, upper=60, step_increment=1, page_increment=10, page_size=1)
        self.ctrl_interval.configure(adj, 1, 0)
        self.ctrl_interval.set_value(settings["interval"])

        self.ctrl_show_values = builder.get_object("show-values")
        self.ctrl_show_values.set_active(settings["show-values"])

        self.ctrl_hover_opens = builder.get_object("hover-opens")
        self.ctrl_hover_opens.set_active(settings["hover-opens"])

        self.ctrl_leave_closes = builder.get_object("leave-closes")
        self.ctrl_leave_closes.set_active(settings["leave-closes"])

        self.ctrl_angle = builder.get_object("angle")
        self.ctrl_angle.set_active_id(str(settings["angle"]))

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(frame)

    def update_controls(self):
        settings = self.panel["controls-settings"]

        if self.ctrl_comp_brightness.get_active():
            if "brightness" not in settings["components"]:
                settings["components"].append("brightness")
        else:
            if "brightness" in settings["components"]:
                settings["components"].remove("brightness")

        settings["backlight-controller"] = self.ctrl_backlight_controller.get_active_id()

        settings["backlight-device"] = self.ctrl_backlight_device.get_text()

        if self.ctrl_comp_volume.get_active():
            if "volume" not in settings["components"]:
                settings["components"].append("volume")
        else:
            if "volume" in settings["components"]:
                settings["components"].remove("volume")

        settings["output-switcher"] = self.ctrl_comp_switcher.get_active()

        if self.ctrl_comp_net.get_active():
            if "net" not in settings["components"]:
                settings["components"].append("net")
        else:
            if "net" in settings["components"]:
                settings["components"].remove("net")

        if self.ctrl_comp_bluetooth.get_active():
            if "bluetooth" not in settings["components"]:
                settings["components"].append("bluetooth")
        else:
            if "bluetooth" in settings["components"]:
                settings["components"].remove("bluetooth")

        if self.ctrl_comp_battery.get_active():
            if "battery" not in settings["components"]:
                settings["components"].append("battery")
        else:
            if "battery" in settings["components"]:
                settings["components"].remove("battery")

        settings["commands"]["net"] = self.ctrl_cdm_net.get_text()
        settings["net-interface"] = self.ctrl_net_name.get_text()
        settings["commands"]["bluetooth"] = self.ctrl_cdm_bluetooth.get_text()
        settings["commands"]["battery"] = self.ctrl_cdm_battery.get_text()
        settings["root-css-name"] = self.ctrl_root_css_name.get_text()
        settings["css-name"] = self.ctrl_css_name.get_text()

        settings["window-width"] = int(self.ctrl_window_width.get_value())
        settings["window-margin-horizontal"] = int(self.ctrl_window_margin_horizontal.get_value())
        settings["window-margin-vertical"] = int(self.ctrl_window_margin_vertical.get_value())
        settings["icon-size"] = int(self.ctrl_icon_size.get_value())
        settings["interval"] = int(self.ctrl_interval.get_value())

        settings["show-values"] = self.ctrl_show_values.get_active()
        settings["hover-opens"] = self.ctrl_hover_opens.get_active()
        settings["leave-closes"] = self.ctrl_leave_closes.get_active()

        try:
            settings["angle"] = float(self.ctrl_angle.get_active_id())
        except:
            settings["angle"] = 0.0

        save_json(self.config, self.file)

    def edit_custom_items(self, item):
        self.load_panel()
        self.edited = "custom-items"
        custom_items_grid = ControlsCustomItems(self.panel, self.config, self.file)

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(custom_items_grid)

    def edit_user_menu(self, item):
        self.load_panel()
        self.edited = "user-menu"
        custom_items_grid = ControlsUserMenu(self.panel, self.config, self.file)

        for item in self.scrolled_window.get_children():
            item.destroy()
        self.scrolled_window.add(custom_items_grid)


def on_pick_btn(btn, entry):
    s = cmd2string("nwg-icon-picker")
    if s:
        entry.set_text(s)


class ControlsCustomItems(Gtk.Frame):
    def __init__(self, panel, config, file):
        check_key(panel, "controls-settings", {})
        self.settings = panel["controls-settings"]
        Gtk.Frame.__init__(self)
        self.set_label("Controls: Custom items")
        self.grid = Gtk.Grid()
        self.grid.set_column_spacing(6)
        self.grid.set_row_spacing(6)
        self.set_label_align(0.5, 0.5)
        self.grid.set_property("margin", 6)
        self.add(self.grid)
        check_key(self.settings, "custom-items", [])
        self.items = self.settings["custom-items"]
        self.icons = panel["icons"]

        self.config = config
        self.file = file

        self.refresh()

    def refresh(self):
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        for i in range(len(self.items)):
            item = self.items[i]

            row = Gtk.ListBoxRow()
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            row.add(vbox)
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            vbox.pack_start(hbox, False, False, 6)

            entry = Gtk.Entry()
            entry.set_width_chars(10)
            entry.set_text(item["name"])
            entry.connect("changed", self.update_value_from_entry, i, "name")
            hbox.pack_start(entry, False, False, 0)

            entry = Gtk.Entry()
            entry.set_width_chars(10)
            entry.set_text(item["icon"])
            update_icon(entry, self.icons)
            entry.connect("changed", self.update_icon, self.icons, i, "icon")
            hbox.pack_start(entry, False, False, 0)

            if is_command("nwg-icon-picker"):
                btn = Gtk.Button.new_from_icon_name("nwg-icon-picker", Gtk.IconSize.MENU)
                btn.set_tooltip_text("Pick an icon")
                btn.connect("clicked", on_pick_btn, entry)
                hbox.pack_start(btn, False, False, 0)

            entry = Gtk.Entry()
            entry.set_width_chars(12)
            entry.set_text(item["cmd"])
            entry.connect("changed", self.update_value_from_entry, i, "cmd")
            hbox.pack_start(entry, True, False, 0)

            btn = Gtk.Button.new_from_icon_name("go-up", Gtk.IconSize.MENU)
            btn.set_always_show_image(True)
            btn.set_sensitive(i > 0)
            btn.connect("clicked", self.move_up, item)
            hbox.pack_start(btn, False, False, 0)

            btn = Gtk.Button.new_from_icon_name("go-down", Gtk.IconSize.MENU)
            btn.set_always_show_image(True)
            btn.set_sensitive(i < len(self.items) - 1)
            btn.connect("clicked", self.move_down, item)
            hbox.pack_start(btn, False, False, 0)

            btn = Gtk.Button.new_from_icon_name("list-remove", Gtk.IconSize.MENU)
            btn.set_always_show_image(True)
            btn.connect("clicked", self.delete, item)
            hbox.pack_start(btn, False, False, 0)

            listbox.add(row)

        # Empty row
        row = Gtk.ListBoxRow()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        row.add(vbox)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(hbox, False, False, 6)

        self.new_name = Gtk.Entry()
        self.new_name.set_width_chars(10)
        self.new_name.set_placeholder_text("label")
        hbox.pack_start(self.new_name, False, False, 0)

        self.new_icon = Gtk.Entry()
        self.new_icon.set_width_chars(10)
        self.new_icon.set_placeholder_text("icon")
        update_icon(self.new_icon, self.icons)
        self.new_icon.connect("changed", update_icon, self.icons)
        hbox.pack_start(self.new_icon, False, False, 0)

        if is_command("nwg-icon-picker"):
            btn = Gtk.Button.new_from_icon_name("nwg-icon-picker", Gtk.IconSize.MENU)
            btn.set_tooltip_text("Pick an icon")
            btn.connect("clicked", on_pick_btn, self.new_icon)
            hbox.pack_start(btn, False, False, 0)

        self.new_command = Gtk.Entry()
        self.new_command.set_width_chars(10)
        self.new_command.set_placeholder_text("command")
        hbox.pack_start(self.new_command, False, False, 0)

        btn = Gtk.Button.new_from_icon_name("list-add", Gtk.IconSize.MENU)
        btn.set_always_show_image(True)
        btn.set_label("Append")
        btn.connect("clicked", self.append)
        hbox.pack_start(btn, True, True, 0)

        listbox.add(row)

        if self.grid.get_child_at(0, 1):
            self.grid.get_child_at(0, 1).destroy()
        self.grid.attach(listbox, 0, 1, 3, 1)

        self.show_all()

    def update_value_from_entry(self, gtk_entry, i, key):
        self.items[i][key] = gtk_entry.get_text()

    def update_icon(self, gtk_entry, icons, i, key):
        icons_path = ""
        if icons == "light":
            icons_path = os.path.join(get_config_dir(), "icons_light")
        elif icons == "dark":
            icons_path = os.path.join(get_config_dir(), "icons_dark")
        name = gtk_entry.get_text()
        gtk_entry.set_icon_from_pixbuf(Gtk.EntryIconPosition.PRIMARY, create_pixbuf(name, 16, icons_path=icons_path))

        self.items[i][key] = gtk_entry.get_text()

    def move_up(self, btn, item):
        old_index = self.items.index(item)
        self.items.insert(old_index - 1, self.items.pop(old_index))
        self.refresh()

    def move_down(self, btn, item):
        old_index = self.items.index(item)
        self.items.insert(old_index + 1, self.items.pop(old_index))
        self.refresh()

    def delete(self, btn, item):
        self.items.remove(item)
        self.refresh()

    def append(self, btn):
        name = self.new_name.get_text()
        icon = self.new_icon.get_text()
        cmd = self.new_command.get_text()
        if name:
            item = {"name": name, "icon": icon, "cmd": cmd}
            self.items.append(item)
        self.refresh()


class ControlsUserMenu(Gtk.Frame):
    def __init__(self, panel, config, file):
        check_key(panel, "controls-settings", {})
        self.settings = panel["controls-settings"]
        Gtk.Frame.__init__(self)
        self.set_label("Controls: User menu")
        self.grid = Gtk.Grid()
        self.grid.set_column_spacing(10)
        self.grid.set_row_spacing(10)
        self.set_label_align(0.5, 0.5)
        self.grid.set_property("margin", 6)
        self.add(self.grid)
        check_key(self.settings, "menu", {})
        check_key(self.settings["menu"], "name", "unnamed")
        check_key(self.settings["menu"], "icon", "")
        check_key(self.settings["menu"], "items", [])

        self.name = self.settings["menu"]["name"]
        self.icon = self.settings["menu"]["icon"]
        self.items = self.settings["menu"]["items"]
        self.icons = panel["icons"]

        self.config = config
        self.file = file

        self.refresh()

    def refresh(self):

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(hbox, False, False, 6)

        label = Gtk.Label()
        label.set_text("Menu name")
        hbox.pack_start(label, False, False, 6)

        entry = Gtk.Entry()
        entry.set_width_chars(10)
        entry.set_text(self.name)
        entry.connect("changed", self.update_prop_from_entry, "name")
        hbox.pack_start(entry, False, False, 0)

        label = Gtk.Label()
        label.set_text("Icon")
        hbox.pack_start(label, True, False, 6)

        entry = Gtk.Entry()
        entry.set_width_chars(20)
        entry.set_text(self.icon)
        update_icon(entry, self.icons)
        entry.connect("changed", self.update_icon, self.icons, "icon")
        hbox.pack_start(entry, False, False, 0)

        self.grid.attach(vbox, 0, 1, 3, 1)

        if is_command("nwg-icon-picker"):
            button_picker = Gtk.Button.new_from_icon_name("nwg-icon-picker", Gtk.IconSize.BUTTON)
            button_picker.set_tooltip_text("Pick an icon")
            button_picker.connect("clicked", on_pick_btn, entry)
            hbox.pack_start(button_picker, False, False, 0)

        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        for i in range(len(self.items)):
            item = self.items[i]

            row = Gtk.ListBoxRow()
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            row.add(vbox)
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            vbox.pack_start(hbox, False, False, 6)

            entry = Gtk.Entry()
            entry.set_width_chars(15)
            entry.set_text(item["name"])
            entry.connect("changed", self.update_value_from_entry, i, "name")
            hbox.pack_start(entry, False, False, 0)

            entry = Gtk.Entry()
            entry.set_width_chars(25)
            entry.set_text(item["cmd"])
            entry.connect("changed", self.update_value_from_entry, i, "cmd")
            hbox.pack_start(entry, False, False, 0)

            btn = Gtk.Button.new_from_icon_name("go-up", Gtk.IconSize.MENU)
            btn.set_always_show_image(True)
            btn.set_sensitive(i > 0)
            btn.connect("clicked", self.move_up, item)
            hbox.pack_start(btn, False, False, 0)

            btn = Gtk.Button.new_from_icon_name("go-down", Gtk.IconSize.MENU)
            btn.set_always_show_image(True)
            btn.set_sensitive(i < len(self.items) - 1)
            btn.connect("clicked", self.move_down, item)
            hbox.pack_start(btn, False, False, 0)

            btn = Gtk.Button.new_from_icon_name("list-remove", Gtk.IconSize.MENU)
            btn.set_always_show_image(True)
            btn.connect("clicked", self.delete, item)
            hbox.pack_start(btn, False, False, 0)

            listbox.add(row)

        # Empty row
        row = Gtk.ListBoxRow()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        row.add(vbox)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(hbox, False, False, 6)

        self.new_name = Gtk.Entry()
        self.new_name.set_width_chars(10)
        self.new_name.set_placeholder_text("label")
        hbox.pack_start(self.new_name, False, False, 0)

        self.new_command = Gtk.Entry()
        self.new_command.set_width_chars(20)
        self.new_command.set_placeholder_text("command")
        hbox.pack_start(self.new_command, False, False, 0)

        btn = Gtk.Button.new_from_icon_name("list-add", Gtk.IconSize.MENU)
        btn.set_always_show_image(True)
        btn.set_label("Append")
        btn.connect("clicked", self.append)
        hbox.pack_start(btn, True, True, 0)

        listbox.add(row)

        if self.grid.get_child_at(0, 2):
            self.grid.get_child_at(0, 2).destroy()
        self.grid.attach(listbox, 0, 2, 3, 1)

        self.show_all()

    def update_prop_from_entry(self, gtk_entry, key):
        self.settings["menu"][key] = gtk_entry.get_text()

    def update_value_from_entry(self, gtk_entry, i, key):
        self.items[i][key] = gtk_entry.get_text()

    def update_icon(self, gtk_entry, icons, key):
        icons_path = ""
        if icons == "light":
            icons_path = os.path.join(get_config_dir(), "icons_light")
        elif icons == "dark":
            icons_path = os.path.join(get_config_dir(), "icons_dark")
        name = gtk_entry.get_text()
        gtk_entry.set_icon_from_pixbuf(Gtk.EntryIconPosition.PRIMARY, create_pixbuf(name, 16, icons_path=icons_path))

        self.update_prop_from_entry(gtk_entry, key)

    def move_up(self, btn, item):
        old_index = self.items.index(item)
        self.items.insert(old_index - 1, self.items.pop(old_index))
        self.refresh()

    def move_down(self, btn, item):
        old_index = self.items.index(item)
        self.items.insert(old_index + 1, self.items.pop(old_index))
        self.refresh()

    def delete(self, btn, item):
        self.items.remove(item)
        self.refresh()

    def append(self, btn):
        name = self.new_name.get_text()
        cmd = self.new_command.get_text()
        if name and cmd:
            item = {"name": name, "cmd": cmd}
            self.items.append(item)
        self.refresh()


def main():
    global configs
    configs = list_configs(config_dir)

    GLib.set_prgname('nwg-panel-config')

    check_commands()

    tree = None
    if sway:
        try:
            from i3ipc import Connection
        except ModuleNotFoundError:
            print("'python-i3ipc' package required on sway, terminating")
            sys.exit(1)

        i3 = Connection()
        tree = i3.get_tree()

    global outputs
    outputs = list_outputs(sway=sway, tree=tree)

    global selector_window
    selector_window = PanelSelector()

    catchable_sigs = set(signal.Signals) - {signal.SIGKILL, signal.SIGSTOP}
    for sig in catchable_sigs:
        signal.signal(sig, signal_handler)

    Gtk.main()


if __name__ == "__main__":
    sys.exit(main())
