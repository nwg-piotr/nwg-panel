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

import nwg_panel.common

try:
    import netifaces
except ModuleNotFoundError:
    pass

try:
    from pyalsa import alsamixer
except:
    pass

try:
    import psutil
except:
    pass


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


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
    # GIMP returns "app_id": null and for some reason "class": "Gimp-2.10" instead of just "gimp".
    # Until the GTK3 version is released, let's make an exception for GIMP.
    if "GIMP" in app_name.upper():
        return "gimp"
    
    for d in nwg_panel.common.app_dirs:
        path = os.path.join(d, "{}.desktop".format(app_name))
        content = None
        if os.path.isfile(path):
            content = load_text_file(path)
        elif os.path.isfile(path.lower()):
            content = load_text_file(path.lower())
        if content:
            for line in content.splitlines():
                if line.upper().startswith("ICON"):
                    return line.split("=")[1]


def local_dir():
    local_dir = os.path.join(os.path.join(os.getenv("HOME"), ".local/share/nwg-panel"))
    if not os.path.isdir(local_dir):
        print("Creating '{}'".format(local_dir))
        os.mkdir(local_dir)

    return local_dir


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


def get_defaults():
    file = os.path.join(local_dir(), "defaults")
    if os.path.isfile(file):
        defaults = load_json(file)
        missing = False
        if "master" not in defaults:
            defaults["master"] = "Master"
            missing = True
            
        if missing:
            save_json(defaults, file)

        return defaults
    else:
        defaults = {
            "master": "Master"
        }
        save_json(defaults, file)

        return defaults


def copy_files(src_dir, dst_dir, restore=False):
    src_files = os.listdir(src_dir)
    for file in src_files:
        if os.path.isfile(os.path.join(src_dir, file)):
            if not os.path.isfile(os.path.join(dst_dir, file)) or restore:
                copyfile(os.path.join(src_dir, file), os.path.join(dst_dir, file))
                print("Copying '{}'".format(os.path.join(dst_dir, file)))


def copy_executors(src_dir, dst_dir):
    src_files = os.listdir(src_dir)
    for file in src_files:
        if os.path.isfile(os.path.join(src_dir, file)) and not os.path.isfile(os.path.join(dst_dir, file)):
            copyfile(os.path.join(src_dir, file), os.path.join(dst_dir, file))
            print("Copying '{}', marking executable".format(os.path.join(dst_dir, file)))
            st = os.stat(os.path.join(dst_dir, file))
            os.chmod(os.path.join(dst_dir, file), st.st_mode | stat.S_IEXEC)


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


def load_string(path):
    try:
        with open(path, 'r') as file:
            data = file.read()
            return data
    except:
        return ""
    

def load_autotiling():
    autotiling = []
    path = os.path.join(temp_dir(), "autotiling")
    try:
        for ws in load_string(path).split(","):
            autotiling.append(int(ws))
    except:
        pass
    return autotiling


def list_outputs(sway=False, silent=False):
    """
    Get output names and geometry from i3 tree, assign to Gdk.Display monitors.
    :return: {"name": str, "x": int, "y": int, "width": int, "height": int, "monitor": Gkd.Monitor}
    """
    outputs_dict = {}
    if sway:
        if not silent:
            print("Running on sway")
        for item in nwg_panel.common.i3.get_tree():
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
    """
    Adds a key w/ default value if missing from the dictionary
    """
    if key not in dictionary:
        dictionary[key] = default_value


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
    vol = 0
    muted = False
    if is_command("pamixer"):
        try:
            vol = int(cmd2string("pamixer --get-volume"))
        except Exception as e:
            eprint(e)
    
        try:
            muted = subprocess.check_output("pamixer --get-mute", shell=True).decode(
                "utf-8").strip() == "true"
        except subprocess.CalledProcessError:
            # the command above returns the 'disabled` status w/ CalledProcessError, exit status 1
            pass
    else:
        eprint("Required 'pamixer' command not found")

    return vol, muted


def list_sinks():
    sinks = []
    if is_command("pamixer"):
        try:
            output = cmd2string("pamixer --list-sinks")
            if output:
                lines = output.splitlines()[1:]
                for line in lines:
                    details = line.split()
                    name = details[1][1:-1]
                    desc = " ".join(details[2:])[1:-1]
                    sinks.append({"name": name, "desc": desc})
        except Exception as e:
            eprint(e)
    else:
        eprint("Required 'pamixer' command not found")

    return sinks


def toggle_mute(*args):
    if is_command("pamixer"):
        vol, muted = get_volume()
        if muted:
            subprocess.call("pamixer -u".split())
        else:
            subprocess.call("pamixer -m".split())
    else:
        eprint("Required 'pamixer' command not found")


def set_volume(slider):
    percent = int(slider.get_value())
    if is_command("pamixer"):
        subprocess.call("pamixer --set-volume {}".format(percent).split())
    else:
        eprint("Required 'pamixer' command not found")


def get_brightness():
    brightness = 0
    try:
        output = cmd2string("light -G")
        brightness = int(round(float(output), 0))
    except:
        pass

    return brightness


def set_brightness(slider):
    value = slider.get_value()
    res = subprocess.call("{} {}".format("light -S", value), shell=True)
    if res != 0:
        print("Couldn't set brightness, is 'light' installed?")


def get_battery():
    try:
        b = psutil.sensors_battery()
        percent = int(round(b.percent, 0))
        charging = b.power_plugged
        seconds = b.secsleft
        if seconds != psutil.POWER_TIME_UNLIMITED and seconds != psutil.POWER_TIME_UNKNOWN:
            time = seconds2string(seconds)
        else:
            time = ""

        return percent, time, charging
    except:
        return 0, "", False


def seconds2string(seconds):
    min, sec = divmod(seconds, 60)
    hrs, min = divmod(min, 60)

    hrs = str(hrs)
    if len(hrs) < 2:
        hrs = "0{}".format(hrs)
    
    min = str(min)
    if len(min) < 2:
        min = "0{}".format(min)

    return "{}:{}".format(hrs, min)


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


def update_image(image, icon_name, icon_size, icons_path=""):
    # In case a full path was given
    if icon_name.startswith("/"):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_name, icon_size, icon_size)
            image.set_from_pixbuf(pixbuf)
        except:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                os.path.join(get_config_dir(), "icons_light/icon-missing.svg"), icon_size, icon_size)
            image.set_from_pixbuf(pixbuf)
    else:
        icon_theme = Gtk.IconTheme.get_default()
        if icons_path:
            path = "{}/{}.svg".format(icons_path, icon_name)
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, icon_size, icon_size)
                if image:
                    image.set_from_pixbuf(pixbuf)
            except:
                try:
                    pixbuf = icon_theme.load_icon(icon_name, icon_size, Gtk.IconLookupFlags.FORCE_SIZE)
                    if image:
                        image.set_from_pixbuf(pixbuf)
                except:
                    pass
        else:
            try:
                pixbuf = icon_theme.load_icon(icon_name, icon_size, Gtk.IconLookupFlags.FORCE_SIZE)
            except:
                path = os.path.join(get_config_dir(), "icons_light/icon-missing.svg")
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, icon_size, icon_size)
            if image:
                image.set_from_pixbuf(pixbuf)
        

def create_pixbuf(icon_name, icon_size, icons_path=""):
    # In case a full path was given
    if icon_name.startswith("/"):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                icon_name, icon_size, icon_size)
            return pixbuf
        except:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                os.path.join(get_config_dir(), "icons_light/icon-missing.svg"), icon_size, icon_size)
            return pixbuf

    icon_theme = Gtk.IconTheme.get_default()
    if icons_path:
        path = "{}/{}.svg".format(icons_path, icon_name)
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                path, icon_size, icon_size)
            return pixbuf
        except:
            try:
                pixbuf = icon_theme.load_icon(icon_name, icon_size, Gtk.IconLookupFlags.FORCE_SIZE)
                return pixbuf
            except:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    os.path.join(get_config_dir(), "icons_light/icon-missing.svg"), icon_size, icon_size)
                return pixbuf
    else:
        try:
            pixbuf = icon_theme.load_icon(icon_name, icon_size, Gtk.IconLookupFlags.FORCE_SIZE)
            return pixbuf
        except:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                os.path.join(get_config_dir(), "icons_light/icon-missing.svg"), icon_size, icon_size)
            return pixbuf


def bt_on():
    try:
        output = subprocess.check_output("bluetoothctl show | awk '/Powered/{print $2}'", shell=True).decode(
            "utf-8").strip()
        return output == "yes"
    except:
        return False


def bt_name():
    try:
        output = subprocess.check_output("bluetoothctl show | awk '/Name/{print $2}'", shell=True).decode("utf-8").strip()
        return output
    except:
        return "undetected"


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


def list_configs(config_dir):
    configs = {}
    entries = os.listdir(config_dir)
    entries.sort()
    for entry in entries:
        path = os.path.join(config_dir, entry)
        if os.path.isfile(path):
            try:
                with open(path, 'r') as f:
                    config = json.load(f)
                configs[path] = config
            except:
                pass

    return configs