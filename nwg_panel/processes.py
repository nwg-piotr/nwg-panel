import os

import psutil
from i3ipc import Connection
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Gio

grid = None
protected = ["systemd", "bash"]

theme = Gtk.IconTheme.get_default()

def handle_keyboard(win, event):
    if event.type == Gdk.EventType.KEY_RELEASE and event.keyval == Gdk.KEY_Escape:
        win.destroy()


def terminate(btn, pid):
    print("Killing {}".format(pid))
    os.kill(pid, 2)


def list_processes(box):
    tree = Connection().get_tree()
    processes = {}

    for proc in psutil.process_iter(['pid', 'ppid', 'name', 'username']):
        if proc.info['username'] == os.getenv('USER') and proc.info['ppid'] == 1:
            processes[proc.info['pid']] = proc.info['name']

    global grid
    if grid:
        grid.destroy()

    grid = Gtk.Grid.new()
    grid.set_row_spacing(6)
    grid.set_column_spacing(6)
    box.pack_start(grid, True, True, 0)

    lbl = Gtk.Label()
    lbl.set_markup("<b>PID</b>")
    lbl.set_property("halign", Gtk.Align.END)
    grid.attach(lbl, 0, 0, 1, 1)

    lbl = Gtk.Label()
    lbl.set_markup("<b>Name</b>")
    lbl.set_property("halign", Gtk.Align.START)
    grid.attach(lbl, 2, 0, 1, 1)

    lbl = Gtk.Label()
    lbl.set_markup("<b>Kill</b>")
    lbl.set_property("halign", Gtk.Align.START)
    grid.attach(lbl, 3, 0, 1, 1)

    idx = 1
    for pid in processes:
        if not tree.find_by_pid(pid):
            lbl = Gtk.Label.new(str(pid))
            lbl.set_property("halign", Gtk.Align.END)
            grid.attach(lbl, 0, idx, 1, 1)

            name = processes[pid]

            if theme.lookup_icon(name, 16, Gtk.IconLookupFlags.FORCE_SYMBOLIC):
                img = Gtk.Image.new_from_icon_name(name, Gtk.IconSize.MENU)
                img.set_property("halign", Gtk.Align.END)
                grid.attach(img, 1, idx, 1, 1)

            lbl = Gtk.Label.new(name)
            lbl.set_property("halign", Gtk.Align.START)
            grid.attach(lbl, 2, idx, 1, 1)



            if processes[pid] not in protected:
                btn = Gtk.Button.new_from_icon_name("gtk-close", Gtk.IconSize.MENU)
                btn.connect("clicked", terminate, pid)
                grid.attach(btn, 3, idx, 1, 1)

            idx += 1
    grid.show_all()
    return True


def main():
    win = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
    win.connect('destroy', Gtk.main_quit)
    win.connect("key-release-event", handle_keyboard)

    box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
    box.set_property("margin", 12)
    win.add(box)

    list_processes(box)

    win.show_all()

    GLib.timeout_add(1000, list_processes, box)
    Gtk.main()


if __name__ == '__main__':
    main()
