import os

import psutil
from i3ipc import Connection
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

from nwg_panel.tools import get_config_dir, load_json, save_json, check_key, eprint

common_settings = {}
protected = ["systemd", "bash"]
grid = Gtk.Grid()

theme = Gtk.IconTheme.get_default()

def handle_keyboard(win, event):
    if event.type == Gdk.EventType.KEY_RELEASE and event.keyval == Gdk.KEY_Escape:
        win.destroy()


def terminate(btn, pid):
    print("Killing {}".format(pid))
    os.kill(pid, 2)


def list_processes(widget, scrolled_window):
    tree = Connection().get_tree()
    processes = {}

    for proc in psutil.process_iter(['pid', 'ppid', 'name', 'username']):
        # if proc.info['username'] == os.getenv('USER') and proc.info['ppid'] == 1:
        processes[proc.info['pid']] = proc.info['name']

    for child in scrolled_window.get_children():
        scrolled_window.remove(child)

    global grid
    if grid:
        grid.destroy()

    grid = Gtk.Grid.new()
    grid.set_row_spacing(6)
    grid.set_column_spacing(6)
    scrolled_window.add(grid)

    lbl = Gtk.Label()
    lbl.set_markup("<b>PID</b>")
    lbl.set_property("halign", Gtk.Align.END)
    grid.attach(lbl, 0, 0, 1, 1)

    lbl = Gtk.Label()
    lbl.set_markup("<b>User</b>")
    lbl.set_property("halign", Gtk.Align.END)
    grid.attach(lbl, 1, 0, 1, 1)

    lbl = Gtk.Label()
    lbl.set_markup("<b>Name</b>")
    lbl.set_property("halign", Gtk.Align.START)
    grid.attach(lbl, 3, 0, 1, 1)

    lbl = Gtk.Label()
    lbl.set_markup("<b>Kill</b>")
    lbl.set_property("halign", Gtk.Align.START)
    grid.attach(lbl, 4, 0, 1, 1)

    idx = 1
    for pid in processes:
        if not tree.find_by_pid(pid) or common_settings["processes-background-only"]:
            lbl = Gtk.Label.new(str(pid))
            lbl.set_property("halign", Gtk.Align.END)
            grid.attach(lbl, 0, idx, 1, 1)

            name = processes[pid]

            if theme.lookup_icon(name, 16, Gtk.IconLookupFlags.FORCE_SYMBOLIC):
                img = Gtk.Image.new_from_icon_name(name, Gtk.IconSize.MENU)
                img.set_property("halign", Gtk.Align.END)
                grid.attach(img, 2, idx, 1, 1)

            lbl = Gtk.Label.new(name)
            lbl.set_property("halign", Gtk.Align.START)
            grid.attach(lbl, 3, idx, 1, 1)

            if processes[pid] not in protected:
                btn = Gtk.Button.new_from_icon_name("gtk-close", Gtk.IconSize.MENU)
                btn.connect("clicked", terminate, pid)
                grid.attach(btn, 4, idx, 1, 1)

            idx += 1
    grid.show_all()
    return True


def on_background_cb(check_button):
    common_settings["processes-background-only"] = check_button.get_active()


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

    scrolled_window = Gtk.ScrolledWindow.new(None, None)
    scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.ALWAYS)
    scrolled_window.set_propagate_natural_width(True)
    scrolled_window.set_propagate_natural_height(True)
    box.pack_start(scrolled_window, True, True, 0)

    hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 12)
    box.pack_start(hbox, False, False, 0)

    cb = Gtk.CheckButton.new_with_label("Background only")
    cb.set_active(common_settings["processes-background-only"])
    cb.connect("toggled", on_background_cb)
    hbox.pack_start(cb, False, False, 6)

    btn = Gtk.Button.new_with_label("Close")
    hbox.pack_end(btn, False, False, 0)
    btn.connect("clicked", Gtk.main_quit)

    btn = Gtk.Button.new_with_label("Refresh")
    hbox.pack_end(btn, False, False, 0)
    btn.connect("clicked", list_processes, scrolled_window)

    list_processes(None, scrolled_window)

    win.show_all()

    # GLib.timeout_add(1000, list_processes, scrolled_window)
    Gtk.main()


if __name__ == '__main__':
    main()
