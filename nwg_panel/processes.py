#!/usr/bin/env python3

"""
nwg-shell helper script to preview system processes
Copyright (c) 2023-2024 Piotr Miller
e-mail: nwg.piotr@gmail.com
GitHub: https://github.com/nwg-piotr/nwg-panel
Project: https://nwg-piotr.github.io/nwg-shell
License: MIT
"""

import json
import os
import socket
import sys
from enum import Enum

import psutil
from i3ipc import Connection
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

from nwg_panel.tools import get_config_dir, load_json, save_json, check_key, eprint

swaysock = os.getenv('SWAYSOCK')
his = os.getenv("HYPRLAND_INSTANCE_SIGNATURE")


class SortOrder(Enum):
    NONE = 0
    PID = 1
    PPID = 2
    NAME = 3
    USERNAME = 4
    CPU_PERCENT = 5
    MEMORY_PERCENT = 6


sort_order = SortOrder.PID

# We need to get_allocated_width of each one inside a function later
btn_pid, btn_ppid, btn_owner, btn_cpu, btn_mem, btn_name = None, None, None, None, None, None,


def hyprctl(cmd):
    # /tmp/hypr moved to $XDG_RUNTIME_DIR/hypr in #5788
    xdg_runtime_dir = os.getenv("XDG_RUNTIME_DIR")
    hypr_dir = f"{xdg_runtime_dir}/hypr" if xdg_runtime_dir and os.path.isdir(
        f"{xdg_runtime_dir}/hypr") else "/tmp/hypr"

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(f"{hypr_dir}/{os.getenv('HYPRLAND_INSTANCE_SIGNATURE')}/.socket.sock")

    s.send(cmd.encode("utf-8"))
    output = s.recv(20480).decode('utf-8')
    s.close()

    return output


if not swaysock and not his:
    eprint("Neither sway nor hyprland socket detected, terminating.")
    sys.exit(1)

W_OWNER = 10
W_NAME = 24

# Fallback icon names dict: win_name -> icon_name
aliases = {
    "Gimp-2.10": "gimp",
    "nwg-panel-config": "nwg-panel"
}

settings = {}  # nwg-panel common settings
scrolled_window = None
grid = Gtk.Grid()
window_lbl = None

theme = Gtk.IconTheme.get_default()


def handle_keyboard(win, event):
    if event.type == Gdk.EventType.KEY_RELEASE and event.keyval == Gdk.KEY_Escape:
        win.destroy()


def terminate(btn, pid):
    print("Terminating {}".format(pid))
    try:
        os.kill(pid, 15)
    except Exception as e:
        eprint(e)

    list_processes()


def list_processes(once=False):
    tree = None
    if swaysock:
        tree = Connection().get_tree()
    elif his:
        output = hyprctl("j/clients")
        clients = json.loads(output)

    processes = {}

    user = os.getenv('USER')
    for proc in psutil.process_iter(['pid', 'ppid', 'name', 'username', 'cpu_percent', 'memory_percent']):
        if proc.info['username'] == os.getenv('USER') or not settings["processes-own-only"]:
            processes[proc.info['pid']] = proc.info

    processes_list = []
    for pid in processes:
        item = {
            "pid": pid,
            "ppid": processes[pid]["ppid"],
            "name": processes[pid]["name"],
            "username": processes[pid]["username"],
            "cpu_percent": processes[pid]["cpu_percent"],
            "memory_percent": processes[pid]["memory_percent"]
        }
        processes_list.append(item)

    if sort_order == SortOrder.PID:
        sorted_list = processes_list  # they are already sorted by PID, no need to sort
    elif sort_order == SortOrder.PPID:
        sorted_list = sorted(processes_list, key=lambda d: d['ppid'])
    elif sort_order == SortOrder.NAME:
        sorted_list = sorted(processes_list, key=lambda d: d['name'].upper())
    elif sort_order == SortOrder.USERNAME:
        sorted_list = sorted(processes_list, key=lambda d: d['username'].upper())
    elif sort_order == SortOrder.CPU_PERCENT:
        sorted_list = sorted(processes_list, key=lambda d: d['cpu_percent'], reverse=True)
    elif sort_order == SortOrder.MEMORY_PERCENT:
        sorted_list = sorted(processes_list, key=lambda d: d['memory_percent'], reverse=True)
    else:
        sorted_list = processes_list

    # At first, we need to add grid to the scrolled window (as in former add_with_viewport).
    # In next iterations, we add the grid directly to already existing viewport, to avoid the scrolled window floating.
    if scrolled_window and scrolled_window.get_children():
        viewport = scrolled_window.get_children()[0]
    else:
        viewport = None

    global grid
    if grid:
        grid.destroy()

    grid = Gtk.Grid.new()
    grid.set_column_spacing(3)

    if viewport:
        viewport.add(grid)
    elif scrolled_window:
        scrolled_window.add(grid)

    idx = 1
    for item in sorted_list:
        cons = None
        mapped = {}
        pid = item['pid']
        if swaysock:
            cons = tree.find_by_pid(pid)
        elif his:
            for client in clients:
                if client["pid"] == pid and client["mapped"]:
                    mapped["pid"] = client["class"]
                    break

        if not cons or not settings["processes-background-only"]:
            lbl = Gtk.Label.new(str(pid))
            lbl.set_xalign(0)
            grid.attach(lbl, 1, idx, 1, 1)

            lbl = Gtk.Label.new(str(processes[pid]["ppid"]))
            lbl.set_xalign(0)
            grid.attach(lbl, 2, idx, 1, 1)

            owner = processes[pid]["username"]
            if len(owner) > W_OWNER - 1:
                owner = "{}…".format(owner[:W_OWNER - 2])
            lbl = Gtk.Label.new(owner)
            lbl.set_xalign(0)
            grid.attach(lbl, 3, idx, 1, 1)

            percent = processes[pid]["cpu_percent"]
            if percent == 0:
                lbl = Gtk.Label.new("{}%".format(str(percent)))
            else:
                lbl = Gtk.Label()
                lbl.set_markup("<b>{}%</b>".format(str(percent)))
            lbl.set_xalign(0)
            grid.attach(lbl, 4, idx, 1, 1)

            percent = processes[pid]["memory_percent"]
            if percent < 1:
                lbl = Gtk.Label.new("{}%".format(str(round(percent, 2))))
            else:
                lbl = Gtk.Label()
                lbl.set_markup("<b>{}%</b>".format(str(round(percent, 2))))
            lbl.set_xalign(0)
            grid.attach(lbl, 5, idx, 1, 1)

            win_name = ""
            if cons:
                if cons[0].app_id:
                    win_name = cons[0].app_id
                elif cons[0].window_class:
                    win_name = cons[0].window_class
                elif cons[0].name:
                    win_name = cons[0].name
                elif cons[0].window_title:
                    win_name = cons[0].window_title
            elif mapped:
                win_name = mapped["pid"]

            if win_name:
                lbl = Gtk.Label.new(" {}".format(win_name))
                lbl.set_xalign(0)
                grid.attach(lbl, 8, idx, 1, 1)

            name = processes[pid]["name"]
            if theme.lookup_icon(name, 16, Gtk.IconLookupFlags.FORCE_SYMBOLIC):
                img = Gtk.Image.new_from_icon_name(name, Gtk.IconSize.MENU)
                img.set_property("halign", Gtk.Align.END)
                grid.attach(img, 6, idx, 1, 1)
            # fallback icon name
            elif win_name and theme.lookup_icon(win_name, 16, Gtk.IconLookupFlags.FORCE_SYMBOLIC):
                img = Gtk.Image.new_from_icon_name(win_name, Gtk.IconSize.MENU)
                img.set_property("halign", Gtk.Align.END)
                grid.attach(img, 6, idx, 1, 1)
            elif win_name and win_name in aliases and theme.lookup_icon(aliases[win_name], 16,
                                                                        Gtk.IconLookupFlags.FORCE_SYMBOLIC):
                img = Gtk.Image.new_from_icon_name(aliases[win_name], Gtk.IconSize.MENU)
                img.set_property("halign", Gtk.Align.END)
                grid.attach(img, 6, idx, 1, 1)

            if len(name) > W_NAME:
                name = "{}…".format(name[:W_NAME - 1])
            lbl = Gtk.Label.new(name)
            lbl.set_width_chars(W_NAME)
            lbl.set_xalign(0)
            grid.attach(lbl, 7, idx, 1, 1)

            if processes[pid]["username"] == user:
                btn = Gtk.Button.new_from_icon_name("gtk-close", Gtk.IconSize.MENU)
                btn.set_property("name", "btn-kill")
                btn.set_property("halign", Gtk.Align.CENTER)
                btn.connect("clicked", terminate, pid)
                grid.attach(btn, 0, idx, 1, 1)

            idx += 1

    # placeholders to align column width with the button box on top
    img = Gtk.Image()
    grid.attach(img, 0, idx + 1, 2, 1)
    img.set_size_request(btn_pid.get_allocated_width(), 0)

    img = Gtk.Image()
    grid.attach(img, 2, idx + 1, 1, 1)
    img.set_size_request(btn_ppid.get_allocated_width(), 0)

    img = Gtk.Image()
    grid.attach(img, 3, idx + 1, 1, 1)
    img.set_size_request(btn_owner.get_allocated_width(), 0)

    img = Gtk.Image()
    grid.attach(img, 4, idx + 1, 1, 1)
    img.set_size_request(btn_cpu.get_allocated_width(), 0)

    img = Gtk.Image()
    grid.attach(img, 5, idx + 1, 1, 1)
    img.set_size_request(btn_mem.get_allocated_width(), 0)

    img = Gtk.Image()
    grid.attach(img, 6, idx + 1, 2, 1)
    img.set_size_request(btn_name.get_allocated_width(), 0)

    grid.show_all()

    if not once:
        return True


def set_sort_order(btn, order):
    global sort_order
    sort_order = order

    btn_pid.set_label("  PID   ")
    btn_ppid.set_label(" PPID  ")
    btn_owner.set_label(" Owner  ")
    btn_cpu.set_label(" CPU%  ")
    btn_mem.set_label(" Mem%  ")
    btn_name.set_label("          Name          ")

    if order == SortOrder.PID:
        btn_pid.set_label("  PID  <")
    if order == SortOrder.PPID:
        btn_ppid.set_label(" PPID <")
    if order == SortOrder.USERNAME:
        btn_owner.set_label(" Owner <")
    if order == SortOrder.CPU_PERCENT:
        btn_cpu.set_label(" CPU% <")
    if order == SortOrder.MEMORY_PERCENT:
        btn_mem.set_label(" Mem% <")
    if order == SortOrder.NAME:
        btn_name.set_label("          Name         <")

    list_processes()


def on_background_cb(check_button):
    settings["processes-background-only"] = check_button.get_active()
    save_json(settings, os.path.join(get_config_dir(), "common-settings.json"))
    if window_lbl:
        window_lbl.set_visible(not settings["processes-background-only"])

    list_processes()


def on_own_cb(check_button):
    settings["processes-own-only"] = check_button.get_active()
    save_json(settings, os.path.join(get_config_dir(), "common-settings.json"))

    list_processes()


def main():
    GLib.set_prgname('nwg-processes')
    global settings
    settings = load_json(os.path.join(get_config_dir(), "common-settings.json"))
    defaults = {
        "processes-background-only": False,
        "processes-own-only": True,
        "processes-interval-ms": 2000
    }
    for key in defaults:
        check_key(settings, key, defaults[key])
    if not swaysock:
        settings["processes-background-only"] = False

    win = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
    win.connect('destroy', Gtk.main_quit)
    win.connect("key-release-event", handle_keyboard)

    box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 6)
    box.set_property("margin", 6)
    box.set_property("vexpand", True)
    wrapper = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
    box.pack_start(wrapper, False, False, 0)
    hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 3)
    wrapper.pack_start(hbox, True, True, 0)

    global btn_pid, btn_ppid, btn_owner, btn_cpu, btn_mem, btn_name

    btn_pid = Gtk.Button.new_with_label("  PID  <")
    btn_pid.connect("clicked", set_sort_order, SortOrder.PID)
    hbox.pack_start(btn_pid, False, False, 0)
    btn_pid.show()

    btn_ppid = Gtk.Button.new_with_label(" PPID  ")
    btn_ppid.connect("clicked", set_sort_order, SortOrder.PPID)
    hbox.pack_start(btn_ppid, False, False, 0)
    btn_ppid.show()

    btn_owner = Gtk.Button.new_with_label(" Owner  ")
    btn_owner.connect("clicked", set_sort_order, SortOrder.USERNAME)
    hbox.pack_start(btn_owner, False, False, 0)

    btn_cpu = Gtk.Button.new_with_label(" CPU%  ")
    btn_cpu.connect("clicked", set_sort_order, SortOrder.CPU_PERCENT)
    hbox.pack_start(btn_cpu, False, False, 0)

    btn_mem = Gtk.Button.new_with_label(" Mem%  ")
    btn_mem.connect("clicked", set_sort_order, SortOrder.MEMORY_PERCENT)
    hbox.pack_start(btn_mem, False, False, 0)

    btn_name = Gtk.Button.new_with_label("          Name          ")
    btn_name.connect("clicked", set_sort_order, SortOrder.NAME)
    hbox.pack_start(btn_name, False, False, 0)

    global window_lbl
    window_lbl = Gtk.Label.new(" Window")
    window_lbl.set_xalign(0)
    hbox.pack_start(window_lbl, False, False, 0)

    win.add(box)

    global scrolled_window
    scrolled_window = Gtk.ScrolledWindow.new(None, None)
    scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scrolled_window.set_propagate_natural_height(True)
    box.pack_start(scrolled_window, True, True, 0)

    dist = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
    dist.set_property("vexpand", True)
    box.pack_start(dist, True, True, 0)

    hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
    hbox.set_property("margin", 6)
    box.pack_start(hbox, False, False, 0)

    img = Gtk.Image.new_from_icon_name("nwg-processes", Gtk.IconSize.LARGE_TOOLBAR)
    hbox.pack_start(img, False, False, 6)

    lbl = Gtk.Label()
    lbl.set_markup("<b>nwg-processes</b>")
    hbox.pack_start(lbl, False, False, 0)

    if swaysock:
        cb = Gtk.CheckButton.new_with_label("Background only")
        cb.set_tooltip_text("Processes that don't belong to the sway tree")
        cb.set_active(settings["processes-background-only"])
        cb.connect("toggled", on_background_cb)
        hbox.pack_start(cb, False, False, 6)

    cb = Gtk.CheckButton.new_with_label("{}'s only".format(os.getenv('USER')))
    cb.set_tooltip_text("Processes that belong to the current $USER")
    cb.set_active(settings["processes-own-only"])
    cb.connect("toggled", on_own_cb)
    hbox.pack_start(cb, False, False, 6)

    btn = Gtk.Button.new_with_label("Close")
    hbox.pack_end(btn, False, False, 0)
    btn.connect("clicked", Gtk.main_quit)

    screen = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    style_context = Gtk.StyleContext()
    style_context.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    css = b""" #btn-kill { padding: 0; border: 0; margin: 0 }
        label { font-family: DejaVu Sans Mono } """
    provider.load_from_data(css)

    win.show_all()

    win.set_size_request(0, 500)

    list_processes()

    if settings["processes-interval-ms"] > 0:
        Gdk.threads_add_timeout(GLib.PRIORITY_DEFAULT_IDLE, settings["processes-interval-ms"], list_processes)
    else:
        GLib.timeout_add(1000, list_processes, True)

    Gtk.main()


if __name__ == '__main__':
    main()
