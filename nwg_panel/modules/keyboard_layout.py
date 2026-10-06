#!/usr/bin/env python3
import json
import os

import gi

from nwg_panel.tools import check_key, update_image, eprint, hyprctl, niri_keyboard_layouts, niri_ipc
from nwg_panel.mango_ipc import get_mango_ipc

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk, GLib

# virtual keyboards (zwp_virtual_keyboard_v1) in `hyprctl devices`, by Hyprland version:
# "hl-virtual-keyboard[-<client>]" since 0.42, "cvirtualkeyboard" in 0.40-0.41, the wlroots name before
HYPR_VIRTUAL_KEYBOARDS = ("hl-virtual-keyboard", "cvirtualkeyboard", "wlr_virtual_keyboard_v1")


def on_enter_notify_event(widget, event):
    widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
    widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)


def on_leave_notify_event(widget, event, *args):
    widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
    widget.unset_state_flags(Gtk.StateFlags.SELECTED)


def on_menu_popped_up(arg0, arg1, arg2, arg3, arg4, widget):
    widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
    widget.unset_state_flags(Gtk.StateFlags.SELECTED)


class KeyboardLayout(Gtk.EventBox):
    def __init__(self, settings, icons_path):
        self.settings = settings
        self.icons_path = icons_path
        Gtk.EventBox.__init__(self)
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(self.box)
        self.image = Gtk.Image()
        self.label = Gtk.Label.new("")
        self.icon_path = None

        if os.getenv("SWAYSOCK"):
            from i3ipc import Connection
            self.i3 = Connection()
            self.compositor = "sway"
        elif os.getenv("HYPRLAND_INSTANCE_SIGNATURE"):
            self.compositor = "Hyprland"
        elif os.getenv("NIRI_SOCKET"):
            self.compositor = "niri"
        elif os.getenv("MANGO_INSTANCE_SIGNATURE"):
            self.compositor = "mango"
        else:
            self.compositor = ""
            eprint("KeyboardLayout module only supports sway, Hyprland, Niri and Mango")

        # set before anything that may call refresh(): it must work with no keyboard listed
        check_key(settings, "keyboard-device-sway", "")
        check_key(settings, "keyboard-device-hyprland", "")
        self.device_name = settings["keyboard-device-sway"] if self.compositor == "sway" else settings[
            "keyboard-device-hyprland"]
        check_key(settings, "labels", {})
        self.keyboards = []
        self.kb_layouts = []

        if self.compositor:
            self.keyboards = self.list_keyboards()
            # on Hyprland, a headless Pi has no keyboard until a VNC client connects, and `hyprctl devices` may
            # time out at session start: build the UI anyway, the label follows on the next layout event
            if self.keyboards or self.compositor in ("niri", "Hyprland"):
                self.keyboard_names = []
                for k in self.keyboards:
                    if self.compositor == "Hyprland":
                        self.keyboard_names.append(k["name"])
                    elif self.compositor == "mango":
                        self.keyboard_names.append(k["name"])
                    # On sway some devices may be listed twice, let's add them just once
                    elif k.identifier not in self.keyboard_names:
                        self.keyboard_names.append(k.identifier)

                self.kb_layouts = self.get_kb_layouts()

                check_key(settings, "root-css-name", "root-executor")
                check_key(settings, "css-name", "executor-label")
                check_key(settings, "icon-placement", "left")
                check_key(settings, "icon-size", 16)
                check_key(settings, "show-icon", True)
                check_key(settings, "interval", 0)
                check_key(settings, "tooltip-text", "LMB: Next layout, RMB: Menu")
                check_key(settings, "angle", 0.0)

                self.label.set_angle(settings["angle"])

                if settings["angle"] != 0.0:
                    self.box.set_orientation(Gtk.Orientation.VERTICAL)

                update_image(self.image, "input-keyboard", self.settings["icon-size"], self.icons_path)

                self.set_property("name", settings["root-css-name"])
                if settings["css-name"]:
                    self.label.set_property("name", settings["css-name"])
                else:
                    self.label.set_property("name", "executor-label")

                if settings["tooltip-text"]:
                    self.set_tooltip_text(settings["tooltip-text"])

                self.connect('button-release-event', self.on_button_release)
                self.connect('enter-notify-event', on_enter_notify_event)
                self.connect('leave-notify-event', on_leave_notify_event)

                self.build_box()
                label = self.get_current_layout()
                if label:
                    self.label.set_text(self.settings["labels"].get(label, label))
                self.show_all()
                if self.compositor == "Hyprland":
                    # updated on Hyprland "activelayout" events (see hypr_watcher), no polling needed
                    import nwg_panel.common
                    nwg_panel.common.kb_layouts_list.append(self)
            else:
                print("KeyboardLayout module: failed listing devices, won't create UI, sorry.")

        self.refresh()

    def list_keyboards(self):
        if self.compositor == "Hyprland":
            # hyprctl returns "" on timeout (busy compositor, session start): keep what we had
            try:
                devices = json.loads(hyprctl("j/devices"))
            except ValueError:
                devices = None
            keyboards = devices.get("keyboards", []) if isinstance(devices, dict) else None
            if not isinstance(keyboards, list):
                eprint("KeyboardLayout: no valid reply to `hyprctl devices`")
                return self.keyboards
        elif self.compositor == "sway":
            inputs = self.i3.get_inputs()
            keyboards = []
            for i in inputs:
                if i.type == "keyboard":
                    keyboards.append(i)
        elif self.compositor == "mango":
            keyboards = []
            devices = get_mango_ipc("get all-devices")["devices"]
            for d in devices:
                if "keyboard" in d["types"]:
                    keyboards.append(d)
        else:
            keyboards = []

        return keyboards

    @staticmethod
    def device_layouts(keyboard):
        # `hyprctl devices -j` reports the layouts configured for each keyboard ("fr,us"); per-device
        # rules make it differ from the global `input:kb_layout`
        layout = keyboard.get("layout") if isinstance(keyboard, dict) else None
        return [name.strip() for name in layout.split(",") if name.strip()] if isinstance(layout, str) else []

    def hypr_real_keyboards(self):
        """The keyboards this module reads and switches: all but the virtual ones (wayvnc, on-screen keyboards,
        input methods). The layout of a virtual keyboard belongs to its client: the client sends its own layout
        group with every modifier change and may bring a keymap of its own, while `hyprctl devices` still reports
        the configured `layout` list for it. A layout set from here only lasts until that client's next modifier,
        and until then what is typed through it is read in a layout it did not choose."""
        real = [k for k in self.keyboards if not str(k.get("name", "")).startswith(HYPR_VIRTUAL_KEYBOARDS)]
        # nothing but virtual keyboards: they are all we have
        return real or self.keyboards

    def hypr_reference_keyboard(self):
        """The keyboard that stands for the current layout when no device is configured: the main (last used)
        one. A virtual keyboard is "main" as soon as a VNC client connects; a real keyboard is used then."""
        keyboards = self.hypr_real_keyboards()
        ref = next((k for k in self.keyboards if k.get("main")), None)
        if ref is not None and not any(k is ref for k in keyboards):
            # the real keyboard in the same state, if any: an input method's keyboard mirrors the one typed on
            state = (ref.get("active_layout_index"), ref.get("active_keymap"))
            ref = next((k for k in keyboards if (k.get("active_layout_index"), k.get("active_keymap")) == state), None)
        if ref is None:
            ref = next((k for k in keyboards if "keyboard" in str(k.get("name", ""))),
                       keyboards[0] if keyboards else None)
        return ref

    def get_kb_layouts(self):
        if self.compositor == "Hyprland":
            # the menu index is sent to the configured device when there is one: list that device's layouts
            ref = next((k for k in self.keyboards if k.get("name") == self.device_name), None) \
                if self.device_name else None
            if ref is None:
                ref = self.hypr_reference_keyboard()
            layouts = self.device_layouts(ref) if ref is not None else []
            if layouts:
                return layouts
            o = hyprctl("j/getoption input:kb_layout")
            try:
                option = json.loads(o)
            except ValueError:
                return []
            if option and "str" in option:
                return option["str"].split(",")
            return []
        elif self.compositor == "sway":
            layout_names = []
            if self.keyboards:
                for k in self.keyboards:
                    for name in k.xkb_layout_names:
                        if name not in layout_names:
                            layout_names.append(name)
            return layout_names
        elif self.compositor == "niri":
            return niri_keyboard_layouts()["names"]
        elif self.compositor == "mango":
            # we don't seem to have a way to get all layouts on Mango
            return []
        else:
            return []

    def get_current_layout(self):
        if self.compositor == "Hyprland":
            if self.device_name:
                for k in self.keyboards:
                    if k["name"] == self.device_name:
                        return k["active_keymap"]
                return "unknown"
            else:
                keyboard = self.hypr_reference_keyboard()
                # no keyboard (headless, before a VNC client connects): nothing to show
                return keyboard.get("active_keymap", "") if keyboard else ""
        elif self.compositor == "sway":
            for k in self.keyboards:
                if "keyboard" in k.identifier:
                    return k.xkb_active_layout_name
                return self.keyboards[0].xkb_active_layout_name
            return "unknown"
        elif self.compositor == "niri":
            nkl = niri_keyboard_layouts()
            return nkl["names"][nkl["current_idx"]]
        elif self.compositor == "mango":
            return get_mango_ipc("get keyboardlayout").get("layout", "")
        else:
            return "unknown"

    def update_label(self):
        self.keyboards = self.list_keyboards()
        txt = self.get_current_layout()
        if txt:
            txt = self.settings["labels"].get(txt, txt)
            # may be called from a background thread: touch GTK widgets from the main loop only
            GLib.idle_add(self.label.set_text, txt)
        return False

    def refresh(self, *args):
        self.update_label()

    def build_box(self):
        if self.settings["show-icon"] and self.settings["icon-placement"] == "left":
            self.box.pack_start(self.image, False, False, 3)
        self.box.pack_start(self.label, False, False, 3)
        if self.settings["show-icon"] and self.settings["icon-placement"] != "left":
            self.box.pack_start(self.image, False, False, 3)

    def hypr_switch_all(self, arg):
        """Switch every real keyboard, one request each: `switchxkblayout all` would also set the virtual
        keyboards (see hypr_real_keyboards), and only exists since Hyprland 0.43."""
        for k in self.hypr_real_keyboards():
            if k.get("name"):
                hyprctl(f"switchxkblayout {k['name']} {arg}")

    def on_left_click(self):
        if self.compositor == "Hyprland":
            if self.device_name:
                # apply to selected device
                hyprctl(f"switchxkblayout {self.device_name} next")
            else:
                # apply to all real keyboards, including those plugged in after the panel started, and keep them
                # in sync: next layout relative to the reference keyboard (the one used last)
                self.keyboards = self.list_keyboards()
                ref = self.hypr_reference_keyboard()
                # `active_layout_index` is reported since Hyprland 0.51 only; before that, an absolute index would
                # always be computed from 0 and the click would be stuck on the second layout: use `next`
                if ref is not None and isinstance(ref.get("active_layout_index"), int):
                    # the layouts of the reference keyboard (per-device config), not the global option. With fewer
                    # than two of them (device rule with a single layout, empty list) an absolute index would pin
                    # every keyboard on the same layout for good: let each keyboard go to its own next one
                    n = len(self.device_layouts(ref))
                    self.hypr_switch_all((ref["active_layout_index"] + 1) % n if n > 1 else "next")
                else:
                    self.hypr_switch_all("next")
        elif self.compositor == "sway":
            # apply to all devices of type:keyboard
            self.i3.command(f'input type:keyboard xkb_switch_layout next')
        elif self.compositor == "niri":
            command = {"Action":{"SwitchLayout":{"layout":"Next"}}}
            niri_ipc(json.dumps(command), is_json=True)
        elif self.compositor == "mango":
            get_mango_ipc("dispatch  switch_keyboard_layout")

        self.update_label()

    def on_menu_item(self, item, idx):
        if self.compositor == "Hyprland":
            if self.device_name:
                # apply to selected device
                hyprctl(f'switchxkblayout {self.device_name} {idx}')
            else:
                # apply to all real keyboards, including those plugged in after the panel started
                self.keyboards = self.list_keyboards()
                self.hypr_switch_all(idx)
        elif self.compositor == "sway":
            # apply to all devices of type:keyboard
            self.i3.command(f'input type:keyboard xkb_switch_layout {idx}')
        elif self.compositor == "niri":
            command = {"Action":{"SwitchLayout":{"layout":{"Index":idx}}}}
            niri_ipc(json.dumps(command), is_json=True)

        self.update_label()

    def on_right_click(self):
        if self.compositor == "Hyprland":
            # keyboards plugged in (or a devices reply that timed out at start) since the last listing
            self.keyboards = self.list_keyboards()
            self.kb_layouts = self.get_kb_layouts()
        if self.kb_layouts:
            menu = Gtk.Menu()
            menu.connect("popped-up", on_menu_popped_up, self)
            for i in range(len(self.kb_layouts)):
                item = Gtk.MenuItem.new_with_label(self.kb_layouts[i])
                item.connect("activate", self.on_menu_item, i)
                menu.append(item)
            menu.set_reserve_toggle_size(False)
            menu.show_all()
            menu.popup_at_widget(self.label, Gdk.Gravity.STATIC, Gdk.Gravity.STATIC, None)


    def on_button_release(self, widget, event):
        if event.button == 1:
            self.on_left_click()
        elif event.button == 3:
            self.on_right_click()
