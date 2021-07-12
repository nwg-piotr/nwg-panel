#!/usr/bin/env python3

import threading
import subprocess

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GLib, GtkLayerShell

from nwg_panel.tools import check_key, get_brightness, set_brightness, get_volume, set_volume, get_battery, \
    get_interface, update_image, bt_adr, eprint, list_sinks, toggle_mute

from nwg_panel.common import commands


class Controls(Gtk.EventBox):
    def __init__(self, settings, position, alignment, width, monitor=None, icons_path=""):
        self.settings = settings
        self.position = position
        self.alignment = alignment
        self.icons_path = icons_path
        Gtk.EventBox.__init__(self)

        check_key(settings, "show-values", True)
        check_key(settings, "icon-size", 16)
        check_key(settings, "interval", 1)
        check_key(settings, "icon-size", 16)
        check_key(settings, "hover-opens", True)
        check_key(settings, "leave-closes", True)
        check_key(settings, "css-name", "controls-label")
        check_key(settings, "components", ["net", "brightness", "volume", "battery"])
        check_key(settings, "net-interface", "")

        self.set_property("name", "controls-label")

        self.icon_size = settings["icon-size"]

        self.net_icon_name = "view-refresh-symbolic"
        self.net_image = Gtk.Image.new_from_icon_name(self.net_icon_name, Gtk.IconSize.MENU)
        self.net_label = Gtk.Label() if settings["show-values"] else None
        self.net_ip_addr = None

        self.bri_icon_name = "view-refresh-symbolic"
        self.bri_image = Gtk.Image.new_from_icon_name(self.bri_icon_name, Gtk.IconSize.MENU)
        self.bri_label = Gtk.Label() if settings["show-values"] else None
        self.bri_value = 0

        self.vol_icon_name = "view-refresh-symbolic"
        self.vol_image = Gtk.Image.new_from_icon_name(self.vol_icon_name, Gtk.IconSize.MENU)
        self.vol_label = Gtk.Label() if settings["show-values"] else None
        self.vol_value = 0
        self.vol_muted = False

        self.bt_icon_name = "view-refresh-symbolic"
        self.bt_image = Gtk.Image.new_from_icon_name(self.bt_icon_name, Gtk.IconSize.MENU)
        self.bt_label = Gtk.Label() if settings["show-values"] else None
        self.bt_name = ""

        self.bat_icon_name = "view-refresh-symbolic"
        self.bat_image = Gtk.Image.new_from_icon_name(self.bat_icon_name, Gtk.IconSize.MENU)
        self.bat_label = Gtk.Label() if settings["show-values"] else None
        self.bat_value = 0
        self.bat_time = ""
        self.bat_charging = False

        self.pan_image = Gtk.Image()
        update_image(self.pan_image, "pan-down-symbolic", self.icon_size, self.icons_path)

        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(self.box)

        self.popup_window = PopupWindow(self, position, alignment, settings, width, monitor=monitor,
                                        icons_path=self.icons_path)

        self.connect('button-press-event', self.on_button_press)
        self.connect('enter-notify-event', self.on_enter_notify_event)
        self.connect('leave-notify-event', self.on_leave_notify_event)

        self.build_box()
        self.refresh()

        if "battery" in settings["components"]:
            self.refresh_bat()

        if settings["interval"] > 0:
            Gdk.threads_add_timeout_seconds(GLib.PRIORITY_LOW, settings["interval"], self.refresh)

        if "battery" in settings["components"]:
            Gdk.threads_add_timeout_seconds(GLib.PRIORITY_LOW, 5, self.refresh_bat)

    def build_box(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.box.pack_start(box, False, False, 6)

        if "brightness" in self.settings["components"]:
            box.pack_start(self.bri_image, False, False, 4)
            if self.bri_label:
                box.pack_start(self.bri_label, False, False, 0)

        if "volume" in self.settings["components"]:
            box.pack_start(self.vol_image, False, False, 4)
            if self.vol_label:
                box.pack_start(self.vol_label, False, False, 0)

        if "net" in self.settings["components"] and self.settings["net-interface"]:
            if commands["netifaces"]:
                box.pack_start(self.net_image, False, False, 4)
                if self.net_label:
                    box.pack_start(self.net_label, False, False, 0)
            else:
                print("'netifaces' python module not found")

        if "bluetooth" in self.settings["components"] and commands["pybluez"]:
            box.pack_start(self.bt_image, False, False, 4)
            if self.bt_label:
                box.pack_start(self.bt_label, False, False, 0)

        if "battery" in self.settings["components"]:
            box.pack_start(self.bat_image, False, False, 4)
            if self.bat_label:
                box.pack_start(self.bat_label, False, False, 0)

        box.pack_start(self.pan_image, False, False, 4)

    def refresh_output(self):
        if "net" in self.settings["components"] and self.settings["net-interface"]:
            self.net_ip_addr = get_interface(self.settings["net-interface"])
            GLib.idle_add(self.update_net, self.net_ip_addr)

        if commands["pybluez"]:
            adr = bt_adr()
            if "bluetooth" in self.settings["components"]:
                GLib.idle_add(self.update_bt, adr)

        if "brightness" in self.settings["components"]:
            try:
                GLib.idle_add(self.update_brightness)
            except Exception as e:
                print(e)

        if "volume" in self.settings["components"] and commands["pamixer"]:
            try:
                GLib.idle_add(self.update_volume)
            except Exception as e:
                print(e)

        return False

    def refresh_bat_output(self):
        if "battery" in self.settings["components"]:
            try:
                self.bat_value, self.bat_time, self.bat_charging = get_battery()
                GLib.idle_add(self.update_battery, self.bat_value, self.bat_charging)
            except Exception as e:
                print(e)

    def refresh(self):
        thread = threading.Thread(target=self.refresh_output)
        thread.daemon = True
        thread.start()

        return True

    # No point in checking battery data more often that every 5 seconds
    def refresh_bat(self):
        thread = threading.Thread(target=self.refresh_bat_output)
        thread.daemon = True
        thread.start()
        return True

    def update_net(self, ip):
        icon_name = "network-wired-symbolic" if ip else "network-wired-disconnected-symbolic"
        if icon_name != self.net_icon_name:
            update_image(self.net_image, icon_name, self.icon_size, self.icons_path)
            self.net_icon_name = icon_name

        if self.net_label:
            self.net_label.set_text("{}".format(self.settings["net-interface"]))

    def update_bt(self, adr):
        icon_name = "bluetooth-active-symbolic" if adr != "off" else "bluetooth-disabled-symbolic"
        if icon_name != self.bt_icon_name:
            update_image(self.bt_image, icon_name, self.icon_size, self.icons_path)
            self.bt_icon_name = icon_name

        self.bt_name = adr
        if self.bt_label:
            self.bt_label.set_text(adr)

    def update_brightness(self):
        value = get_brightness()
        icon_name = bri_icon_name(value)

        if icon_name != self.bri_icon_name:
            update_image(self.bri_image, icon_name, self.icon_size, self.icons_path)
            self.bri_icon_name = icon_name

        self.bri_value = value
        if self.bri_label:
            self.bri_label.set_text("{}%".format(value))

    def update_volume(self):
        self.vol_value, self.vol_muted = get_volume()
        icon_name = vol_icon_name(self.vol_value, self.vol_muted)

        if icon_name != self.vol_icon_name:
            update_image(self.vol_image, icon_name, self.settings["icon-size"], self.icons_path)
            self.vol_icon_name = icon_name

        if self.vol_label:
            self.vol_label.set_text("{}%".format(self.vol_value))

    def update_battery(self, value, charging):
        icon_name = bat_icon_name(value, charging)

        if icon_name != self.bat_icon_name:
            update_image(self.bat_image, icon_name, self.icon_size, self.icons_path)
            self.bat_icon_name = icon_name

        if self.bat_label:
            self.bat_label.set_text("{}%".format(value))

    def on_button_press(self, w, event):
        if not self.popup_window.get_visible():
            self.popup_window.show_all()
            if self.popup_window.sink_box:
                self.popup_window.sink_box.hide()
            if self.popup_window.menu_box:
                self.popup_window.menu_box.hide()
        else:
            self.popup_window.hide()
        return False

    def on_enter_notify_event(self, widget, event):
        if self.settings["hover-opens"]:
            if not self.popup_window.get_visible():
                self.popup_window.show_all()
                if self.popup_window.sink_box:
                    self.popup_window.sink_box.hide()
                if self.popup_window.menu_box:
                    self.popup_window.menu_box.hide()
        else:
            self.get_style_context().set_state(Gtk.StateFlags.SELECTED)

        # cancel popup window close, as it's probably unwanted ATM
        self.popup_window.on_window_enter()

        return True

    def on_leave_notify_event(self, widget, event):
        self.get_style_context().set_state(Gtk.StateFlags.NORMAL)
        return True


class PopupWindow(Gtk.Window):
    def __init__(self, parent, position, alignment, settings, width, monitor=None, icons_path=""):
        Gtk.Window.__init__(self, type_hint=Gdk.WindowTypeHint.NORMAL)
        GtkLayerShell.init_for_window(self)
        if monitor:
            GtkLayerShell.set_monitor(self, monitor)

        check_key(settings, "css-name", "controls-window")
        self.parent = parent
        
        self.set_property("name", settings["css-name"])
        self.icon_size = settings["icon-size"]
        self.icons_path = icons_path

        self.settings = settings
        self.position = position

        self.net_icon_name = ""

        self.menu_box = None
        self.sink_box = None

        self.bri_scale = None
        self.vol_scale = None
        
        self.src_tag = 0
        
        self.connect("show", self.on_window_show)

        check_key(settings, "output-switcher", False)
        self.sinks = []
        if commands["pamixer"] and settings["output-switcher"] and commands["pamixer"]:
            self.sinks = list_sinks()

        eb = Gtk.EventBox()
        eb.set_above_child(False)
        if settings["leave-closes"]:
            self.connect("leave_notify_event", self.on_window_exit)
            self.connect("enter_notify_event", self.on_window_enter)

        outer_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        eb.add(outer_vbox)
        self.add(eb)

        outer_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        Gtk.Widget.set_size_request(outer_hbox, width, 10)
        outer_vbox.pack_start(outer_hbox, True, True, 20)

        v_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer_hbox.pack_start(v_box, True, True, 20)

        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        # GtkLayerShell.set_keyboard_interactivity(self, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, settings["window-margin"])
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, settings["window-margin"])
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, settings["window-margin"])
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT, settings["window-margin"])

        if alignment == "left":
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        else:
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        if position == "bottom":
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
        else:
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)

        check_key(settings, "commands", {"battery": "", "net": ""})

        add_sep = False
        if "brightness" in settings["components"]:
            inner_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            v_box.pack_start(inner_hbox, False, False, 0)

            self.bri_icon_name = "view-refresh-symbolic"
            self.bri_image = Gtk.Image.new_from_icon_name(self.bri_icon_name, Gtk.IconSize.MENU)

            inner_hbox.pack_start(self.bri_image, False, False, 6)

            self.bri_scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.HORIZONTAL, min=0, max=100, step=1)
            self.bri_scale.connect("value-changed", self.set_bri)

            inner_hbox.pack_start(self.bri_scale, True, True, 5)
            add_sep = True

        if "volume" in settings["components"] and commands["pamixer"]:
            inner_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            v_box.pack_start(inner_hbox, False, False, 6)

            self.vol_icon_name = "view-refresh-symbolic"
            self.vol_image = Gtk.Image.new_from_icon_name(self.vol_icon_name, Gtk.IconSize.MENU)

            if self.parent.vol_icon_name != self.vol_icon_name:
                update_image(self.vol_image, self.parent.vol_icon_name, self.icon_size, self.icons_path)
                self.vol_icon_name = self.parent.vol_icon_name

            eb = Gtk.EventBox()
            eb.connect("enter_notify_event", self.on_enter_notify_event)
            eb.connect("leave_notify_event", self.on_leave_notify_event)
            eb.connect("button-press-event", self.toggle_mute)
            eb.add(self.vol_image)
            inner_hbox.pack_start(eb, False, False, 6)

            self.vol_scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.HORIZONTAL, min=0, max=100, step=1)
            self.vol_scale.set_value(self.parent.vol_value)
            self.vol_scale.connect("value-changed", self.set_vol)

            inner_hbox.pack_start(self.vol_scale, True, True, 5)
            if commands["pamixer"] and settings["output-switcher"]:
                pactl_eb = Gtk.EventBox()
                image = Gtk.Image()
                pactl_eb.add(image)
                pactl_eb.connect("enter_notify_event", self.on_enter_notify_event)
                pactl_eb.connect("leave_notify_event", self.on_leave_notify_event)
                update_image(image, "pan-down-symbolic", self.icon_size, self.icons_path)
                inner_hbox.pack_end(pactl_eb, False, False, 5)

                self.sink_box = SinkBox()
                pactl_eb.connect('button-press-event', self.sink_box.switch_visibility)
                v_box.pack_start(self.sink_box, False, False, 0)

            add_sep = True

        if add_sep:
            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            v_box.pack_start(sep, True, True, 10)

        if "net" in settings["components"] and commands["netifaces"] and settings["net-interface"]:
            event_box = Gtk.EventBox()
            if "net" in settings["commands"] and settings["commands"]["net"]:
                event_box.connect("enter_notify_event", self.on_enter_notify_event)
                event_box.connect("leave_notify_event", self.on_leave_notify_event)

                event_box.connect('button-press-event', self.launch, settings["commands"]["net"])

            inner_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            inner_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            inner_vbox.pack_start(inner_hbox, True, True, 6)
            v_box.pack_start(event_box, True, True, 0)

            self.net_icon_name = "view-refresh-symbolic"
            self.net_image = Gtk.Image.new_from_icon_name(self.net_icon_name, Gtk.IconSize.MENU)

            icon_name = "network-wired-symbolic" if self.parent.net_ip_addr else "network-wired-disconnected-symbolic"

            if icon_name != self.net_icon_name:
                update_image(self.net_image, icon_name, self.icon_size, self.icons_path)
                self.net_icon_name = icon_name

            inner_hbox.pack_start(self.net_image, False, False, 6)

            self.net_label = Gtk.Label("{}: {}".format(settings["net-interface"], self.parent.net_ip_addr))
            inner_hbox.pack_start(self.net_label, False, True, 6)

            if "net" in settings["commands"] and settings["commands"]["net"]:
                img = Gtk.Image()
                update_image(img, "pan-end-symbolic", self.icon_size, self.icons_path)
                inner_hbox.pack_end(img, False, True, 4)

            event_box.add(inner_vbox)

        if "bluetooth" in settings["components"] and commands["pybluez"]:
            event_box = Gtk.EventBox()
            if "bluetooth" in settings["commands"] and settings["commands"]["bluetooth"]:
                event_box.connect("enter_notify_event", self.on_enter_notify_event)
                event_box.connect("leave_notify_event", self.on_leave_notify_event)

                event_box.connect('button-press-event', self.launch, settings["commands"]["bluetooth"])

            inner_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            inner_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            inner_vbox.pack_start(inner_hbox, True, True, 6)
            v_box.pack_start(event_box, True, True, 0)

            self.bt_icon_name = "view-refresh-symbolic"
            self.bt_image = Gtk.Image.new_from_icon_name(self.bt_icon_name, Gtk.IconSize.MENU)

            inner_hbox.pack_start(self.bt_image, False, False, 6)

            self.bt_label = Gtk.Label()
            inner_hbox.pack_start(self.bt_label, False, True, 6)

            if "bluetooth" in settings["commands"] and settings["commands"]["bluetooth"]:
                img = Gtk.Image()
                update_image(img, "pan-end-symbolic", self.icon_size, self.icons_path)
                inner_hbox.pack_end(img, False, True, 4)

            event_box.add(inner_vbox)

        if "battery" in settings["components"]:
            event_box = Gtk.EventBox()
            if "battery" in settings["commands"] and settings["commands"]["battery"]:
                event_box.connect("enter_notify_event", self.on_enter_notify_event)
                event_box.connect("leave_notify_event", self.on_leave_notify_event)

                event_box.connect('button-press-event', self.launch, settings["commands"]["battery"])

            inner_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            inner_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            inner_vbox.pack_start(inner_hbox, True, True, 6)
            v_box.pack_start(event_box, True, True, 0)

            self.bat_icon_name = "view-refresh-symbolic"
            self.bat_image = Gtk.Image.new_from_icon_name(self.bat_icon_name, Gtk.IconSize.MENU)

            inner_hbox.pack_start(self.bat_image, False, False, 6)

            self.bat_label = Gtk.Label()
            inner_hbox.pack_start(self.bat_label, False, True, 6)

            if "battery" in settings["commands"] and settings["commands"]["battery"]:
                img = Gtk.Image()
                update_image(img, "pan-end-symbolic", self.icon_size, self.icons_path)
                inner_hbox.pack_end(img, False, True, 4)

            event_box.add(inner_vbox)

        check_key(settings, "custom-items", [])
        if settings["custom-items"]:
            for item in settings["custom-items"]:
                check_key(item, "name", "undefined")
                check_key(item, "icon", "")
                check_key(item, "cmd", "")
                c_item = self.custom_item(item["name"], item["icon"], item["cmd"])
                v_box.pack_start(c_item, True, True, 2)

        check_key(settings, "menu", {})
        if settings["menu"]:
            template = settings["menu"]

            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            v_box.pack_start(sep, True, True, 10)

            e_box = Gtk.EventBox()
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            e_box.add(box)
            inner_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            box.pack_start(inner_hbox, True, True, 6)
            v_box.pack_start(e_box, True, True, 0)

            img = Gtk.Image()
            update_image(img, template["icon"], self.icon_size, self.icons_path)
            inner_hbox.pack_start(img, False, False, 6)

            check_key(template, "name", "Menu name")
            label = Gtk.Label(template["name"])
            inner_hbox.pack_start(label, False, False, 6)

            check_key(template, "items", [])
            if template["items"]:
                img = Gtk.Image()
                update_image(img, "pan-down-symbolic", self.icon_size, self.icons_path)
                inner_hbox.pack_end(img, False, True, 5)

                e_box.connect("enter-notify-event", self.on_enter_notify_event)
                e_box.connect("leave-notify-event", self.on_leave_notify_event)

                self.menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
                v_box.pack_start(self.menu_box, False, False, 0)
                for item in template["items"]:
                    eb = Gtk.EventBox()
                    vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
                    hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
                    vb.pack_start(hb, False, False, 3)
                    i = Gtk.Label(item["name"])
                    hb.pack_start(i, False, False, self.icon_size + 18)
                    eb.add(vb)
                    eb.connect("enter_notify_event", self.on_enter_notify_event)
                    eb.connect("leave_notify_event", self.on_leave_notify_event)
                    eb.connect("button-press-event", self.launch, item["cmd"])
                    self.menu_box.pack_start(eb, False, False, 0)

                e_box.connect('button-press-event', self.switch_menu_box)

        Gdk.threads_add_timeout(GLib.PRIORITY_LOW, 500, self.refresh)

    def on_window_exit(self, w, e):
        if self.get_visible():
            self.src_tag = GLib.timeout_add_seconds(1, self.hide_and_clear_tag)
        return True

    def hide_and_clear_tag(self):
        self.hide()
        self.src_tag = 0

    def on_window_enter(self, *args):
        if self.src_tag > 0:
            GLib.Source.remove(self.src_tag)
            self.src_tag = 0
        return True

    def on_window_show(self, *args):
        self.src_tag = 0
        self.refresh

    def switch_menu_box(self, widget, event):
        if self.menu_box.get_visible():
            self.menu_box.hide()
        else:
            self.menu_box.show_all()

    def refresh_sinks(self, *args):
        if  commands["pamixer"]:
            self.sinks = list_sinks()

    def toggle_mute(self, e, slider):
        toggle_mute()
        self.parent.refresh()
        self.refresh()

    def custom_item(self, name, icon, cmd):
        eb = Gtk.EventBox()

        v_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        h_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        v_box.pack_start(h_box, False, False, 6)
        eb.add(v_box)

        image = Gtk.Image()
        update_image(image, icon, self.icon_size, self.icons_path)
        h_box.pack_start(image, False, True, 6)

        label = Gtk.Label(name)
        h_box.pack_start(label, False, True, 4)

        if cmd:
            eb.connect("enter_notify_event", self.on_enter_notify_event)
            eb.connect("leave_notify_event", self.on_leave_notify_event)
            eb.connect('button-press-event', self.launch, cmd)

            img = Gtk.Image()
            update_image(img, "pan-end-symbolic", self.icon_size, self.icons_path)
            h_box.pack_end(img, False, True, 4)

        return eb

    def refresh(self, *args):
        if self.get_visible():
            self.refresh_sinks()
            if "net" in self.settings["components"] and commands["netifaces"] and self.settings["net-interface"]:
                if self.parent.net_icon_name != self.net_icon_name:
                    update_image(self.net_image, self.parent.net_icon_name, self.icon_size, self.icons_path)
                    self.net_icon_name = self.parent.net_icon_name

                ip_addr = "disconnected" if not self.parent.net_ip_addr else self.parent.net_ip_addr
                self.net_label.set_text("{}: {}".format(self.settings["net-interface"], ip_addr))

            if "bluetooth" in self.settings["components"] and commands["pybluez"]:
                if self.parent.bt_icon_name != self.bt_icon_name:
                    update_image(self.bt_image, self.parent.bt_icon_name, self.icon_size, self.icons_path)
                    self.bt_icon_name = self.parent.bt_icon_name

                if self.bt_label:
                    self.bt_label.set_text(self.parent.bt_name)

            if "battery" in self.settings["components"]:
                if self.parent.bat_icon_name != self.bat_icon_name:
                    update_image(self.bat_image, self.parent.bat_icon_name, self.icon_size, self.icons_path)
                    self.bat_icon_name = self.parent.bat_icon_name

                self.bat_label.set_text("{}% {}".format(self.parent.bat_value, self.parent.bat_time))

            if "volume" in self.settings["components"] and commands["pamixer"]:
                if self.parent.vol_icon_name != self.vol_icon_name:
                    update_image(self.vol_image, self.parent.vol_icon_name, self.icon_size, self.icons_path)
                    self.vol_icon_name = self.parent.vol_icon_name

                self.vol_scale.set_value(self.parent.vol_value)

            if "brightness" in self.settings["components"]:
                if self.parent.bri_icon_name != self.bri_icon_name:
                    update_image(self.bri_image, self.parent.bri_icon_name, self.icon_size, self.icons_path)
                    self.bri_icon_name = self.parent.bri_icon_name

                self.bri_scale.set_value(self.parent.bri_value)

        return True

    def on_enter_notify_event(self, widget, event):
        widget.get_style_context().set_state(Gtk.StateFlags.SELECTED)
        return True

    def on_leave_notify_event(self, widget, event):
        widget.get_style_context().set_state(Gtk.StateFlags.NORMAL)
        return True

    def set_bri(self, slider):
        set_brightness(slider)
        self.parent.bri_value = int(slider.get_value())

    def set_vol(self, slider):
        set_volume(slider)
        self.parent.vol_value = int(slider.get_value())

    def close_win(self, w, e):
        self.hide()

    def handle_keyboard(self, w, e):
        if e.type == Gdk.EventType.KEY_RELEASE and e.keyval == Gdk.KEY_Escape:
            self.close_win(w, e)
        return e

    def launch(self, w, e, cmd):
        print("Executing '{}'".format(cmd))
        subprocess.Popen('exec {}'.format(cmd), shell=True)
        self.hide()


class SinkBox(Gtk.Box):
    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.sinks = None
        self.refresh()

    def refresh(self):
        for item in self.get_children():
            item.destroy()
        if commands["pamixer"]:
            self.sinks = list_sinks()
            for sink in self.sinks:
                eb = Gtk.EventBox()
                eb.connect("enter_notify_event", self.on_enter_notify_event)
                eb.connect("leave_notify_event", self.on_leave_notify_event)
                eb.connect('button-press-event', self.switch_sink, sink["name"])
                vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
                vbox.pack_start(hbox, True, True, 4)
                desc = sink["desc"]
                if len(desc) > 26:
                    desc = "{}\u2026".format(desc[:26])
                label = Gtk.Label(desc)
                hbox.pack_start(label, True, True, 0)
                eb.add(vbox)
                self.pack_start(eb, False, False, 0)

    def switch_visibility(self, *args):
        if self.get_visible():
            self.hide()
        else:
            self.refresh()
            self.show_all()

    def on_enter_notify_event(self, widget, event):
        widget.get_style_context().set_state(Gtk.StateFlags.SELECTED)

    def on_leave_notify_event(self, widget, event):
        widget.get_style_context().set_state(Gtk.StateFlags.NORMAL)

    def switch_sink(self, w, e, sink):
        if commands["pactl"]:
            print("Sink: '{}'".format(sink))
            subprocess.Popen('exec pactl set-default-sink "{}"'.format(sink), shell=True)
        else:
            eprint("Couldn't switch sinks, 'pactl' (libpulse) not found")
        self.hide()


def bri_icon_name(value):
    icon_name = "display-brightness-low-symbolic"
    if value > 70:
        icon_name = "display-brightness-high-symbolic"
    elif value > 30:
        icon_name = "display-brightness-medium-symbolic"

    return icon_name


def vol_icon_name(value, muted):
    icon_name = "audio-volume-muted-symbolic"
    if not muted:
        if value is not None:
            if value > 70:
                icon_name = "audio-volume-high-symbolic"
            elif value > 30:
                icon_name = "audio-volume-medium-symbolic"
            else:
                icon_name = "audio-volume-low-symbolic"
        else:
            icon_name = "audio-volume-muted-symbolic"

    return icon_name


def bat_icon_name(value, is_charging):
    icon_name = "battery-empty-symbolic"
    if is_charging:
        if value > 95:
            icon_name = "battery-full-charging-symbolic"
        elif value > 50:
            icon_name = "battery-good-charging-symbolic"
        elif value > 20:
            icon_name = "battery-low-charging-symbolic"
    else:
        if value > 95:
            icon_name = "battery-full-symbolic"
        elif value > 50:
            icon_name = "battery-good-symbolic"
        elif value > 20:
            icon_name = "battery-low-symbolic"

    return icon_name


def bt_icon_name(is_on):
    icon_name = "bluetooth-active-symbolic" if is_on else "bluetooth-disabled-symbolic"

    return icon_name
