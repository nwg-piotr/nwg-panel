import os

import psutil
from i3ipc import Connection
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

from nwg_panel.tools import get_config_dir, load_json, save_json, check_key, eprint

W_PID = 10
W_PPID = 10
W_OWNER = 10
W_CPU = 7
W_MEM = 7
W_NAME = 24
W_WINDOW = 24

common_settings = {}
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

    list_processes(None)


def list_processes(widget):
    tree = Connection().get_tree()
    processes = {}

    user = os.getenv('USER')
    for proc in psutil.process_iter(['pid', 'ppid', 'name', 'username', 'cpu_percent', 'memory_percent']):
        if proc.info['username'] == os.getenv('USER') or not common_settings["processes-own-only"]:
            processes[proc.info['pid']] = proc.info

    if scrolled_window and scrolled_window.get_children():
        viewport = scrolled_window.get_children()[0]
    else:
        viewport = None

    global grid
    if grid:
        grid.destroy()

    grid = Gtk.Grid.new()
    grid.set_row_spacing(3)
    grid.set_row_homogeneous(True)

    if viewport:
        viewport.add(grid)
    else:
        scrolled_window.add(grid)

    idx = 1
    for pid in processes:
        cons = tree.find_by_pid(pid)
        if not cons or not common_settings["processes-background-only"]:
            lbl = Gtk.Label.new(str(pid))
            lbl.set_width_chars(W_PID)
            lbl.set_xalign(0)
            grid.attach(lbl, 1, idx, 1, 1)

            lbl = Gtk.Label.new(str(processes[pid]["ppid"]))
            lbl.set_width_chars(W_PPID)
            lbl.set_xalign(0)
            grid.attach(lbl, 2, idx, 1, 1)

            owner = processes[pid]["username"]
            if len(owner) > W_OWNER - 1:
                owner = "{}…".format(owner[:W_OWNER - 2])
            lbl = Gtk.Label.new(owner)
            lbl.set_width_chars(W_OWNER)
            lbl.set_xalign(0)
            grid.attach(lbl, 3, idx, 1, 1)

            percent = processes[pid]["cpu_percent"]
            if percent == 0:
                lbl = Gtk.Label.new("{}%".format(str(percent)))
            else:
                lbl = Gtk.Label()
                lbl.set_markup("<b>{}</b>".format(str(percent)))
            lbl.set_width_chars(W_CPU)
            lbl.set_xalign(0)
            grid.attach(lbl, 4, idx, 1, 1)

            lbl = Gtk.Label.new("{}%".format(str(round(processes[pid]["memory_percent"], 2))))
            lbl.set_width_chars(W_MEM)
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

            if win_name:
                lbl = Gtk.Label.new(win_name)
                lbl.set_width_chars(W_WINDOW)
                lbl.set_xalign(0)
                grid.attach(lbl, 8, idx, 1, 1)

            name = processes[pid]["name"]
            if theme.lookup_icon(name, 16, Gtk.IconLookupFlags.FORCE_SYMBOLIC):
                img = Gtk.Image.new_from_icon_name(name, Gtk.IconSize.MENU)
                img.set_property("name", "icon")
                img.set_property("halign", Gtk.Align.END)
                grid.attach(img, 6, idx, 1, 1)
            # fallback icon name
            elif win_name and theme.lookup_icon(win_name, 16, Gtk.IconLookupFlags.FORCE_SYMBOLIC):
                img = Gtk.Image.new_from_icon_name(win_name, Gtk.IconSize.MENU)
                img.set_property("name", "icon")
                img.set_property("halign", Gtk.Align.END)
                grid.attach(img, 6, idx, 1, 1)

            if len(name) > W_NAME - 1:
                name = "{}…".format(name[:W_NAME - 2])
            lbl = Gtk.Label.new(name)
            lbl.set_width_chars(W_NAME)
            lbl.set_xalign(0)
            grid.attach(lbl, 7, idx, 1, 1)

            if processes[pid]["username"] == user:
                btn = Gtk.Button.new_from_icon_name("gtk-close", Gtk.IconSize.MENU)
                btn.set_property("name", "btn-kill")
                btn.set_property("hexpand", False)
                btn.set_property("halign", Gtk.Align.START)
                btn.connect("clicked", terminate, pid)
                grid.attach(btn, 0, idx, 1, 1)

            idx += 1

    grid.show_all()

    return True


def on_background_cb(check_button):
    common_settings["processes-background-only"] = check_button.get_active()
    if window_lbl:
        window_lbl.set_visible(not common_settings["processes-background-only"])
    list_processes(None)


def on_own_cb(check_button):
    common_settings["processes-own-only"] = check_button.get_active()
    list_processes(None)


def main():
    GLib.set_prgname('nwg-processes')
    global common_settings
    common_settings = load_json(os.path.join(get_config_dir(), "common-settings.json"))
    defaults = {
        "processes-background-only": False,
        "processes-own-only": True
    }
    for key in defaults:
        check_key(common_settings, key, defaults[key])
    eprint("Common settings", common_settings)

    win = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
    win.connect('destroy', Gtk.main_quit)
    win.connect("key-release-event", handle_keyboard)

    box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 6)
    box.set_property("margin", 6)
    box.set_property("vexpand", True)
    win.add(box)

    wrapper = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
    wrapper.set_property("name", "header")
    box.pack_start(wrapper, False, False, 0)
    desc_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
    wrapper.pack_start(desc_box, False, True, 0)

    img = Gtk.Image()
    img.set_property("name", "img-empty")
    desc_box.pack_start(img, False, False, 0)

    lbl = Gtk.Label.new("PID")
    lbl.set_width_chars(W_PID)
    lbl.set_xalign(0)
    desc_box.pack_start(lbl, False, False, 0)

    lbl = Gtk.Label.new("PPID")
    lbl.set_width_chars(W_PPID)
    lbl.set_xalign(0)
    desc_box.pack_start(lbl, False, False, 0)

    lbl = Gtk.Label.new("Owner")
    lbl.set_width_chars(W_OWNER)
    lbl.set_xalign(0)
    desc_box.pack_start(lbl, False, False, 0)

    lbl = Gtk.Label.new("CPU%")
    lbl.set_width_chars(W_CPU)
    lbl.set_xalign(0)
    desc_box.pack_start(lbl, True, True, 0)

    lbl = Gtk.Label.new("Mem%")
    lbl.set_width_chars(W_MEM)
    lbl.set_xalign(0)
    desc_box.pack_start(lbl, True, True, 0)

    img = Gtk.Image()
    img.set_property("name", "icon")
    desc_box.pack_start(img, True, True, 0)

    lbl = Gtk.Label.new("Name")
    lbl.set_width_chars(W_NAME)
    lbl.set_xalign(0)
    desc_box.pack_start(lbl, True, True, 0)

    global window_lbl
    window_lbl = Gtk.Label.new("Window")
    window_lbl.set_width_chars(W_WINDOW)
    window_lbl.set_xalign(0)
    desc_box.pack_start(window_lbl, True, True, 0)

    global scrolled_window
    scrolled_window = Gtk.ScrolledWindow.new(None, None)
    scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scrolled_window.set_propagate_natural_height(True)
    box.pack_start(scrolled_window, True, True, 0)

    dist = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
    dist.set_property("vexpand", True)
    box.pack_start(dist, True, True, 0)

    hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
    hbox.set_property("margin", 6)
    box.pack_start(hbox, False, False, 0)

    img = Gtk.Image.new_from_icon_name("nwg-processes", Gtk.IconSize.LARGE_TOOLBAR)
    hbox.pack_start(img, False, False, 0)

    lbl = Gtk.Label()
    lbl.set_markup("<b>nwg-processes</b>")
    hbox.pack_start(lbl, False, False, 0)

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

    screen = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    style_context = Gtk.StyleContext()
    style_context.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    css = b""" #header { background-color: rgba(0, 0, 0, 0.3) }
        #icon { margin-right: 6px }
        #img-empty { margin-right: 15px; border: 1px }
        #btn-kill { padding: 0; border: 0; margin-right: 6px }
        label { font-family: DejaVu Sans Mono, monospace } """
    provider.load_from_data(css)

    win.show_all()

    list_processes(None)
    Gdk.threads_add_timeout(GLib.PRIORITY_DEFAULT_IDLE, 2000, list_processes, None)

    Gtk.main()


if __name__ == '__main__':
    main()
