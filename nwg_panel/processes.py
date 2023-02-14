import os

import psutil
from i3ipc import Connection
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

from nwg_panel.tools import get_config_dir, load_json, save_json, check_key, eprint

common_settings = {}
scrolled_window = None
grid = Gtk.Grid()

theme = Gtk.IconTheme.get_default()


def handle_keyboard(win, event):
    if event.type == Gdk.EventType.KEY_RELEASE and event.keyval == Gdk.KEY_Escape:
        win.destroy()


def terminate(btn, pid):
    print("Terminating {}".format(pid))
    try:
        print(os.kill(pid, 15))
    except Exception as e:
        eprint(e)
    # Wait a second for children processes to die
    GLib.timeout_add(1000, list_processes, None)


def list_processes(widget):
    tree = Connection().get_tree()
    processes = {}

    user = os.getenv('USER')
    for proc in psutil.process_iter(['pid', 'ppid', 'name', 'username']):
        if proc.info['username'] == os.getenv('USER') or not common_settings["processes-own-only"]:
            processes[proc.info['pid']] = proc.info

    for child in scrolled_window.get_children():
        scrolled_window.remove(child)

    global grid
    if grid:
        grid.destroy()

    grid = Gtk.Grid.new()
    grid.set_row_spacing(3)
    grid.set_row_homogeneous(True)
    grid.set_column_spacing(6)
    scrolled_window.add(grid)

    lbl = Gtk.Label()
    lbl.set_markup("<b>PID</b>")
    lbl.set_property("halign", Gtk.Align.END)
    grid.attach(lbl, 1, 0, 1, 1)

    lbl = Gtk.Label()
    lbl.set_markup("<b>Owner</b>")
    lbl.set_property("halign", Gtk.Align.END)
    grid.attach(lbl, 2, 0, 1, 1)

    lbl = Gtk.Label()
    lbl.set_markup("<b>Name</b>")
    lbl.set_property("halign", Gtk.Align.START)
    grid.attach(lbl, 4, 0, 1, 1)

    lbl = Gtk.Label()
    lbl.set_markup("<b>Window</b>")
    lbl.set_property("halign", Gtk.Align.START)
    grid.attach(lbl, 5, 0, 1, 1)

    idx = 1
    for pid in processes:
        cons = tree.find_by_pid(pid)
        if not cons or not common_settings["processes-background-only"]:
            lbl = Gtk.Label.new(str(pid))
            lbl.set_property("halign", Gtk.Align.END)
            grid.attach(lbl, 1, idx, 1, 1)

            lbl = Gtk.Label.new(processes[pid]["username"])
            lbl.set_property("halign", Gtk.Align.END)
            grid.attach(lbl, 2, idx, 1, 1)

            name = processes[pid]["name"]
            if theme.lookup_icon(name, 16, Gtk.IconLookupFlags.FORCE_SYMBOLIC):
                img = Gtk.Image.new_from_icon_name(name, Gtk.IconSize.MENU)
                img.set_property("halign", Gtk.Align.END)
                grid.attach(img, 3, idx, 1, 1)

            lbl = Gtk.Label.new(name)
            lbl.set_property("halign", Gtk.Align.START)
            grid.attach(lbl, 4, idx, 1, 1)

            if processes[pid]["username"] == user:
                btn = Gtk.Button.new_from_icon_name("gtk-close", Gtk.IconSize.MENU)
                btn.connect("clicked", terminate, pid)
                grid.attach(btn, 0, idx, 1, 1)

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

            if win_name:
                lbl = Gtk.Label.new(win_name)
                lbl.set_property("halign", Gtk.Align.START)
                grid.attach(lbl, 5, idx, 1, 1)

            idx += 1
    scrolled_window.show_all()
    scrolled_window.get_vadjustment().set_value(0)


def on_background_cb(check_button):
    common_settings["processes-background-only"] = check_button.get_active()
    list_processes(None)


def on_own_cb(check_button):
    common_settings["processes-own-only"] = check_button.get_active()
    list_processes(None)


def main():
    GLib.set_prgname('nwg-processes')
    global common_settings
    common_settings = load_json(os.path.join(get_config_dir(), "common-settings.json"))
    defaults = {
        "processes-background-only": True,
        "processes-own-only": True
    }
    for key in defaults:
        check_key(common_settings, key, defaults[key])
    eprint("Common settings", common_settings)

    win = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
    win.connect('destroy', Gtk.main_quit)
    win.connect("key-release-event", handle_keyboard)

    box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 6)
    box.set_property("margin", 12)
    win.add(box)

    global scrolled_window
    scrolled_window = Gtk.ScrolledWindow.new(None, None)
    scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.ALWAYS)
    scrolled_window.set_propagate_natural_width(True)
    scrolled_window.set_propagate_natural_height(True)
    box.pack_start(scrolled_window, True, True, 0)

    hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 12)
    box.pack_start(hbox, False, False, 0)

    cb = Gtk.CheckButton.new_with_label("Background only")
    cb.set_tooltip_text("Processes that don't belong to the sway tree")
    cb.set_active(common_settings["processes-background-only"])
    cb.connect("toggled", on_background_cb)
    hbox.pack_start(cb, False, False, 6)

    cb = Gtk.CheckButton.new_with_label("{}'s only".format(os.getenv('USER')))
    cb.set_tooltip_text("Processes that belong to the current $USER")
    cb.set_active(common_settings["processes-own-only"])
    cb.connect("toggled", on_own_cb)
    hbox.pack_start(cb, False, False, 6)

    btn = Gtk.Button.new_with_label("Close")
    hbox.pack_end(btn, False, False, 0)
    btn.connect("clicked", Gtk.main_quit)

    btn = Gtk.Button.new_with_label("Refresh")
    hbox.pack_end(btn, False, False, 0)
    btn.connect("clicked", list_processes)

    win.show_all()

    list_processes(None)

    Gtk.main()


if __name__ == '__main__':
    main()
