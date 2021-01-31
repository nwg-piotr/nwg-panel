#!/usr/bin/env python3

import os
import sys
import json
import subprocess
import stat

import gi

gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk, GdkPixbuf
from shutil import copyfile

import common

try:
    import netifaces
except ModuleNotFoundError:
    pass

try:
    from pyalsa import alsamixer
except:
    pass


def temp_dir():
    if os.getenv("TMPDIR"):
        return os.getenv("TMPDIR")
    elif os.getenv("TEMP"):
        return os.getenv("TEMP")
    elif os.getenv("TMP"):
        return os.getenv("TMP")

    return "/tmp"


def get_app_dirs():
    desktop_dirs = []

    home = os.getenv("HOME")
    xdg_data_home = os.getenv("XDG_DATA_HOME")
    xdg_data_dirs = os.getenv("XDG_DATA_DIRS") if os.getenv("XDG_DATA_DIRS") else "/usr/local/share/:/usr/share/"

    if xdg_data_home:
        desktop_dirs.append(os.path.join(xdg_data_home, "applications"))
    else:
        if home:
            desktop_dirs.append(os.path.join(home, ".local/share/applications"))

    for d in xdg_data_dirs.split(":"):
        desktop_dirs.append(os.path.join(d, "applications"))

    # Add flatpak dirs if not found in XDG_DATA_DIRS
    flatpak_dirs = [os.path.join(home, ".local/share/flatpak/exports/share/applications"),
                    "/var/lib/flatpak/exports/share/applications"]
    for d in flatpak_dirs:
        if d not in desktop_dirs:
            desktop_dirs.append(d)

    return desktop_dirs


def get_icon(app_name):
    for d in common.app_dirs:
        path = os.path.join(d, "{}.desktop".format(app_name))
        content = None
        if os.path.isfile(path):
            content = load_text_file(path)
        elif os.path.isfile(path.lower()):
            content = load_text_file(path.lower())
        if content:
            for line in content.splitlines():
                if line.startswith("Icon="):
                    return line.split("=")[1]


def get_config_dir():
    """
    Determine config dir path, create if not found, then create sub-dirs
    :return: config dir path
    """
    xdg_config_home = os.getenv('XDG_CONFIG_HOME')
    config_home = xdg_config_home if xdg_config_home else os.path.join(os.getenv("HOME"), ".config")
    config_dir = os.path.join(config_home, "nwg-panel")
    if not os.path.isdir(config_dir):
        print("Creating '{}'".format(config_dir))
        os.mkdir(config_dir)

    # Icon folders to store user-defined icon replacements
    folder = os.path.join(config_dir, "icons_light")
    if not os.path.isdir(folder):
        print("Creating '{}'".format(folder))
        os.mkdir(folder)

    folder = os.path.join(config_dir, "icons_dark")
    if not os.path.isdir(os.path.join(folder)):
        print("Creating '{}'".format(folder))
        os.mkdir(folder)

    folder = os.path.join(config_dir, "executors")
    if not os.path.isdir(os.path.join(folder)):
        print("Creating '{}'".format(folder))
        os.mkdir(folder)

    return config_dir


def copy_files(src_dir, dst_dir):
    src_files = os.listdir(src_dir)
    for file in src_files:
        if not os.path.isfile(os.path.join(dst_dir, file)):
            copyfile(os.path.join(src_dir, file), os.path.join(dst_dir, file))
            print("Copying '{}'".format(os.path.join(dst_dir, file)))


def copy_executors(src_dir, dst_dir):
    src_files = os.listdir(src_dir)
    for file in src_files:
        if not os.path.isfile(os.path.join(dst_dir, file)):
            f = os.path.join(dst_dir, file)
            copyfile(os.path.join(src_dir, file), f)
            print("Copying '{}', marking executable".format(os.path.join(dst_dir, file)))
            st = os.stat(f)
            os.chmod(f, st.st_mode | stat.S_IEXEC)


def load_text_file(path):
    try:
        with open(path, 'r') as file:
            data = file.read()
            return data
    except Exception as e:
        print(e)
        return None


def load_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(e)
        sys.exit(1)


def save_json(src_dict, path):
    with open(path, 'w') as f:
        json.dump(src_dict, f, indent=2)


def save_string(string, file):
    try:
        file = open(file, "wt")
        file.write(string)
        file.close()
    except:
        print("Error writing file '{}'".format(file))


def list_outputs(silent=False):
    """
    Get output names and geometry from i3 tree, assign to Gdk.Display monitors.
    :return: {"name": str, "x": int, "y": int, "width": int, "height": int, "monitor": Gkd.Monitor}
    """
    outputs_dict = {}
    if common.sway:
        if not silent:
            print("Running on sway")
        for item in common.i3.get_tree():
            if item.type == "output" and not item.name.startswith("__"):
                outputs_dict[item.name] = {"x": item.rect.x,
                                           "y": item.rect.y,
                                           "width": item.rect.width,
                                           "height": item.rect.height}
    elif os.getenv('WAYLAND_DISPLAY') is not None:
        if not silent:
            print("Running on Wayland, but not sway")
        if is_command("wlr-randr"):
            lines = subprocess.check_output("wlr-randr", shell=True).decode("utf-8").strip().splitlines()
            if lines:
                name, w, h, x, y = None, None, None, None, None
                for line in lines:
                    if not line.startswith(" "):
                        name = line.split()[0]
                    elif "current" in line:
                        w_h = line.split()[0].split('x')
                        w = int(w_h[0])
                        h = int(w_h[1])
                    elif "Position" in line:
                        x_y = line.split()[1].split(',')
                        x = int(x_y[0])
                        y = int(x_y[1])
                        if name is not None and w is not None and h is not None and x is not None and y is not None:
                            outputs_dict[name] = {'name': name,
                                                  'x': x,
                                                  'y': y,
                                                  'width': w,
                                                  'height': h}
        else:
            print("'wlr-randr' command not found, terminating")
            sys.exit(1)

    display = Gdk.Display.get_default()
    for i in range(display.get_n_monitors()):
        monitor = display.get_monitor(i)
        geometry = monitor.get_geometry()

        for key in outputs_dict:
            if int(outputs_dict[key]["x"]) == geometry.x and int(outputs_dict[key]["y"]) == geometry.y:
                outputs_dict[key]["monitor"] = monitor

    return outputs_dict


def check_key(dictionary, key, default_value):
    # adds a key w/ default value if missing from the dictionary
    if key not in dictionary:
        dictionary[key] = default_value
        # print('Key missing, using default: "{}": {}'.format(key, default_value))
        common.key_missing = True


def cmd2string(cmd):
    try:
        return subprocess.check_output(cmd, shell=True).decode("utf-8").strip()
    except subprocess.CalledProcessError:
        return ""


def is_command(cmd):
    cmd = cmd.split()[0]  # strip arguments
    cmd = "command -v {}".format(cmd)
    try:
        is_cmd = subprocess.check_output(cmd, shell=True).decode("utf-8").strip()
        if is_cmd:
            return True

    except subprocess.CalledProcessError:
        return False


def get_volume():
    vol = None
    switch = False
    if common.dependencies["pyalsa"]:
        mixer = alsamixer.Mixer()
        mixer.attach()
        mixer.load()

        element = alsamixer.Element(mixer, "Master")
        max_vol = element.get_volume_range()[1]
        vol = int(round(element.get_volume() * 100 / max_vol, 0))
        switch = element.get_switch()
        del mixer
    else:
        result = cmd2string(common.commands["set_volume_alt"])
        if result:
            lines = result.splitlines()
            for line in lines:
                if "Front Left:" in line:
                    try:
                        vol = int(line.split()[4][1:-2])
                    except:
                        pass
                    switch = "on" in line.split()[5]
                    break

    return vol, switch


def set_volume(slider):
    percent = slider.get_value()
    if common.dependencies["pyalsa"]:
        mixer = alsamixer.Mixer()
        mixer.attach()
        mixer.load()

        element = alsamixer.Element(mixer, "Master")
        max_vol = element.get_volume_range()[1]
        element.set_volume_all(int(percent * max_vol / 100))
        del mixer
    else:
        cmd = "{} {}% /dev/null 2>&1".format(common.commands["set_volume_alt"], percent)
        subprocess.call(cmd, shell=True)


def get_brightness():
    brightness = 0
    output = cmd2string(common.commands["get_brightness"])
    try:
        brightness = int(round(float(output), 0))
    except:
        pass

    return brightness


def set_brightness(slider):
    value = slider.get_value()
    res = subprocess.call("{} {}".format(common.commands["set_brightness"], value), shell=True)
    if res != 0:
        print("Couldn't set brightness, is 'light' installed?")


def get_battery():
    if common.dependencies["upower"]:
        cmd = common.commands["get_battery"]
    elif common.dependencies["acpi"]:
        cmd = common.commands["get_battery_alt"]
    else:
        return None, None

    msg = ""
    perc_val = 0
    if cmd.split()[0] == "upower":
        bat = []
        try:
            bat = cmd2string(cmd).splitlines()
        except:
            pass
        state, time, percentage = "", "", ""
        for line in bat:
            line = line.strip()
            if "time to empty" in line:
                line = line.replace("time to empty", "time_to_empty")
            parts = line.split()

            if "percentage:" in parts[0]:
                percentage = parts[1]
                perc_val = int(percentage.split("%")[0])
            if "state:" in parts[0]:
                state = parts[1]
            if "time_to_empty:" in parts[0]:
                time = " ".join(parts[1:])
        msg = "{} {} {}".format(percentage, state, time)
    elif cmd.split()[0] == "acpi":
        bat = ""
        try:
            bat = cmd2string(cmd).splitlines()[0]
        except:
            pass
        if bat:
            parts = bat.split()
            msg = " ".join(parts[2:])
            perc_val = int(parts[3].split("%")[0])

    return msg, perc_val


def list_interfaces():
    try:
        return netifaces.interfaces()
    except:
        return []


def get_interface(name):
    try:
        addrs = netifaces.ifaddresses(name)
        list = addrs[netifaces.AF_INET]

        return list[0]["addr"]
    except:
        return None


def player_status():
    status = "install playerctl"
    if is_command("playerctl"):
        try:
            status = cmd2string("playerctl status 2>&1")
        except:
            pass

    return status


def player_metadata():
    data = ""
    try:
        data = cmd2string("playerctl metadata --format '{{artist}} - {{title}}'")
    except:
        pass

    return data


def update_image(image, icon_name, icon_size):
    icon_theme = Gtk.IconTheme.get_default()
    if common.icons_path:
        path = "{}/{}.svg".format(common.icons_path, icon_name)
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                path, icon_size, icon_size)
            if image:
                image.set_from_pixbuf(pixbuf)
        except Exception as e:
            try:
                pixbuf = icon_theme.load_icon(icon_name, icon_size, Gtk.IconLookupFlags.FORCE_SIZE)
                if image:
                    image.set_from_pixbuf(pixbuf)
            except:
                print("update_image :: failed setting image from {}: {}".format(path, e))
    else:
        image.set_from_icon_name(icon_name, Gtk.IconSize.MENU)


def bt_on():
    output = subprocess.check_output("bluetoothctl show | awk '/Powered/{print $2}'", shell=True).decode(
        "utf-8").strip()

    return output == "yes"


def bt_name():
    output = subprocess.check_output("bluetoothctl show | awk '/Name/{print $2}'", shell=True).decode("utf-8").strip()

    return output


def bt_service_enabled():
    result, enabled, active = False, False, False
    if is_command("systemctl"):
        try:
            enabled = subprocess.check_output("systemctl is-enabled bluetooth.service", shell=True).decode(
                "utf-8").strip() == "enabled"
        except subprocess.CalledProcessError:
            # the command above returns the 'disabled` status w/ CalledProcessError, exit status 1
            pass

        try:
            active = subprocess.check_output("systemctl is-active bluetooth.service", shell=True).decode(
                "utf-8").strip() == "active"
        except subprocess.CalledProcessError:
            pass

        result = enabled and active

    return result
