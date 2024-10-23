#!/usr/bin/env python3

import os
import sys
import json
import subprocess
import stat
import time
import socket
import threading
import re
import glob

import gi

import nwg_panel.common

gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk, GdkPixbuf
from shutil import copyfile
from datetime import datetime

import nwg_panel.common

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


# def map_odd_desktop_files():
#     name2icon_dict = {}
#     for d in nwg_panel.common.app_dirs:
#         if os.path.exists(d):
#             for path in os.listdir(d):
#                 if os.path.isfile(os.path.join(d, path)):
#                     if path.endswith(".desktop") and path.count(".") > 1:
#                         try:
#                             content = load_text_file(os.path.join(d, path))
#                         except Exception as e:
#                             eprint(e)
#                         if content:
#                             for line in content.splitlines():
#                                 if line.startswith("[") and not line == "[Desktop Entry]":
#                                     break
#                                 if line.upper().startswith("ICON="):
#                                     icon = line.split("=")[1]
#                                     name2icon_dict[path] = icon
#                                     break
#
#     return name2icon_dict


def get_icon_name(app_name):
    if not app_name:
        return ""
    # the name might've been already found in .desktop files and stored
    if app_name in nwg_panel.common.app_name2icon_name:
        return nwg_panel.common.app_name2icon_name[app_name]

    # GIMP returns "app_id": null and for some reason "class": "Gimp-2.10" instead of just "gimp".
    # Until the GTK3 version is released, let's make an exception for GIMP.
    if "GIMP" in app_name.upper():
        return "gimp"

    for d in nwg_panel.common.app_dirs:
        # This will work if the .desktop file name is app_id.desktop or wm_class.desktop
        path = os.path.join(d, "{}.desktop".format(app_name))
        content = None
        if os.path.isfile(path):
            content = load_text_file(path)
        elif os.path.isfile(path.lower()):
            content = load_text_file(path.lower())
        if content:
            for line in content.splitlines():
                if line.upper().startswith("ICON"):
                    icon_name = line.split("=")[1]
                    # store for further use
                    nwg_panel.common.app_name2icon_name[app_name] = icon_name
                    return icon_name

        # Otherwise, we need to search all .desktop files
        if os.path.isdir(d):
            for a_file in os.listdir(d):
                if app_name.lower() in a_file.lower():
                    path = os.path.join(d, a_file)
                    content = load_text_file(path)
                    if content:
                        for line in content.splitlines():
                            if line.upper().startswith("ICON"):
                                icon_name = line.split("=")[1]
                                # store for further use
                                nwg_panel.common.app_name2icon_name[app_name] = icon_name
                                return icon_name

    # Search the dictionary made of .desktop files that use "reverse DNS"-style names, prepared on startup.
    # see: https://github.com/nwg-piotr/nwg-panel/issues/64
    # !!! This was case-sensitive, boo :/
    # for key in nwg_panel.common.name2icon_dict.keys():
    #     if app_name in key.split("."):
    #         return nwg_panel.common.name2icon_dict[key]

    # if all above fails
    return app_name


def local_dir():
    local_dir = os.path.join(os.path.join(os.getenv("HOME"), ".local/share/nwg-panel"))
    if not os.path.isdir(local_dir):
        print("Creating '{}'".format(local_dir))
        os.makedirs(local_dir, exist_ok=True)

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
        os.makedirs(config_dir, exist_ok=True)

    # Icon folders to store user-defined icon replacements
    folder = os.path.join(config_dir, "icons_light")
    if not os.path.isdir(folder):
        print("Creating '{}'".format(folder))
        os.makedirs(folder, exist_ok=True)

    folder = os.path.join(config_dir, "icons_dark")
    if not os.path.isdir(os.path.join(folder)):
        print("Creating '{}'".format(folder))
        os.makedirs(folder, exist_ok=True)

    folder = os.path.join(config_dir, "icons_color")
    if not os.path.isdir(os.path.join(folder)):
        print("Creating '{}'".format(folder))
        os.makedirs(folder, exist_ok=True)

    folder = os.path.join(config_dir, "executors")
    if not os.path.isdir(os.path.join(folder)):
        print("Creating '{}'".format(folder))
        os.makedirs(folder, exist_ok=True)

    return config_dir


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
        eprint("Error loading json: {}".format(e))
        return {}


def save_json(src_dict, path):
    try:
        with open(path, 'w') as f:
            json.dump(src_dict, f, indent=2)
        return "ok"
    except Exception as e:
        return e


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


def num_active_outputs(outputs):
    a = 0
    for output in outputs:
        if output.active:
            a += 1
    return a


def list_outputs(sway=False, silent=False):
    """
    Get output names and geometry from i3 tree, assign to Gdk.Display monitors.
    :return: {"name": str, "x": int, "y": int, "width": int, "height": int, "monitor": Gkd.Monitor}
    """
    outputs_dict = {}
    if sway:
        try:
            from i3ipc import Connection
        except ModuleNotFoundError:
            print("'python-i3ipc' package required on sway, terminating")
            sys.exit(1)

        i3 = Connection()

        if not silent:
            print("Running on sway")
        outputs = i3.get_outputs()
        for item in outputs:
            outputs_dict[item.name] = {"x": item.rect.x,
                                       "y": item.rect.y,
                                       "width": item.rect.width,
                                       "height": item.rect.height,
                                       "description": f"{item.make} {item.model} {item.serial}",
                                       "monitor": None}

    elif os.getenv('HYPRLAND_INSTANCE_SIGNATURE') is not None:
        if not silent:
            print("Running on Hyprland")
        cmd = "hyprctl -j monitors"
        result = subprocess.check_output(cmd, shell=True).decode("utf-8").strip()
        outputs = json.loads(result)
        for item in outputs:
            outputs_dict[item["name"]] = {"x": item["x"],
                                          "y": item["y"],
                                          "width": int(item["width"] / item["scale"]),
                                          "height": int(item["height"] / item["scale"]),
                                          "description": item["description"],
                                          "monitor": None}
            # swap for rotated displays
            if item["transform"] in [1, 3, 5, 7]:
                outputs_dict[item["name"]]["width"] = item["height"]
                outputs_dict[item["name"]]["height"] = item["width"]

    elif os.getenv('WAYLAND_DISPLAY') is not None:
        if not silent:
            print("Running on Wayland, but neither sway nor Hyprland")
        if nwg_panel.common.commands["wlr-randr"]:
            lines = subprocess.check_output("wlr-randr", shell=True).decode("utf-8").strip().splitlines()
            if lines:
                name, description, w, h, x, y, transform, scale = None, None, None, None, None, None, None, 1.0
                for line in lines:
                    if not line.startswith(" "):
                        name = line.split()[0]
                        description = line.split()[1]
                    elif "current" in line:
                        w_h = line.split()[0].split('x')
                        w = int(w_h[0])
                        h = int(w_h[1])
                    elif "Transform" in line:
                        transform = line.split()[1].strip()
                    elif "Position" in line:
                        x_y = line.split()[1].split(',')
                        x = int(x_y[0])
                        y = int(x_y[1])
                    elif "Scale" in line:
                        try:
                            scale = float(line.split()[1])
                        except ValueError:
                            scale = 1.0

                    if name is not None and w is not None and h is not None and x is not None and y is not None \
                            and transform is not None:
                        if transform == "normal":  # which other values it returns for not rotated displays?
                            outputs_dict[name] = {'name': name,
                                                  'x': x,
                                                  'y': y,
                                                  'width': int(w / scale),
                                                  'height': int(h / scale),
                                                  'transform': transform,
                                                  'description': description,
                                                  'monitor': None}
                        else:
                            outputs_dict[name] = {'name': name,
                                                  'x': x,
                                                  'y': y,
                                                  'width': int(h / scale),
                                                  'height': int(w / scale),
                                                  'transform': transform,
                                                  'description': description,
                                                  'scale': scale,
                                                  'monitor': None}
                        # Each monitor only has a single transform, this is to avoid parsing the same monitor multiple times
                        # Disabled monitors don't have transforms.
                        # Gdk doesn't report disabled monitors, not filtering them would cause crashes
                        transform = None
        else:
            print("'wlr-randr' command not found, terminating")
            sys.exit(1)

    # We used to assign Gdk.Monitor to output on the basis of x and y coordinates, but it no longer works,
    # starting from gtk3-1:3.24.42: all monitors have x=0, y=0. This is most likely a bug, but from now on
    # we must rely on gdk monitors order. Hope it's going to work.
    monitors = []
    display = Gdk.Display.get_default()
    for i in range(display.get_n_monitors()):
        monitor = display.get_monitor(i)
        monitors.append(monitor)

    for key, monitor in zip(outputs_dict.keys(), monitors):
        outputs_dict[key]["monitor"] = monitor

    # map monitor descriptions to output names
    mon_desc2output_name = {}
    for key in outputs_dict:
        if "description" in outputs_dict[key]:
            mon_desc2output_name[outputs_dict[key]["description"]] = key

    return outputs_dict, mon_desc2output_name


def check_key(dictionary, key, default_value):
    """
    Adds a key w/ default value if missing from the dictionary
    """
    if key not in dictionary:
        dictionary[key] = default_value


def cmd2string(cmd):
    process_env = dict(os.environ)
    process_env.update({"LANG": "C.UTF-8"})
    try:
        return subprocess.check_output(cmd, shell=True, env=process_env).decode("utf-8").strip()
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
        pass

    return False


def check_commands():
    for key in nwg_panel.common.commands:
        nwg_panel.common.commands[key] = is_command(key)

    try:
        import requests
        nwg_panel.common.commands["python-requests"] = True
    except ModuleNotFoundError:
        pass


def create_background_task(target, interval, args=(), kwargs=None):
    if kwargs is None:
        kwargs = {}

    def loop_wrapper():
        if interval > 0:
            while True:
                target(*args, **kwargs)
                time.sleep(interval)
        else:
            target(*args, **kwargs)

    thread = threading.Thread(target=loop_wrapper, daemon=True)
    return thread


def get_volume():
    vol = 0
    muted = False
    if nwg_panel.common.commands["pactl"]:
        try:
            output = cmd2string("pactl get-sink-volume @DEFAULT_SINK@")
            volumes = re.findall(r"/\s+(?P<volume>\d+)%\s+/", output)
            if volumes:
                volumes = [int(x) for x in volumes]
                vol = volumes[0]
        except Exception as e:
            eprint(e)

        try:
            output = cmd2string("pactl get-sink-mute @DEFAULT_SINK@").strip().lower()
            muted = output.endswith("yes")
        except Exception as e:
            eprint(e)
    elif nwg_panel.common.commands["pamixer"]:
        try:
            output = cmd2string("pamixer --get-volume")
            if output:
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
        eprint("Couldn't get volume, no 'pamixer' or 'pactl' found")

    return vol, muted


def list_sink_inputs():
    """
    Thanks to @fm16191 for https://github.com/fm16191/pactl-json-parser
    """
    # This used to return localized output, returning unexpected values #327
    # p = subprocess.run("pactl list sink-inputs".split(), capture_output=True)
    # result = p.stdout.decode()

    result = cmd2string("pactl list sink-inputs")

    # Syntax fix
    result = result.replace(u"\xa0", " ")  # Broken encoding for spaces
    result = result.replace(u"\\\"", "\"")  # Replacing all espaced doublequote to inline singlequote (JSON compliant)
    result = result.replace(u"\"", "\'")

    sinks = dict()

    for oline in result.split("\n"):
        if oline == "":
            continue  # Skip empty lines
        # Indentation indicates the JSON structure
        indent = oline.count('\t')
        line = oline[indent:]
        if indent == 0:  # Get sink name
            sink_name = line.split("#")[-1]
            sinks[sink_name] = {}
        elif indent == 1:  # Get sink object
            if line.startswith("        "):  # Output is over two lines
                sinks[sink_name][name] = sinks[sink_name][name] + " " + line.strip()
            else:
                ii = line.index(":")
                name = line[:ii].strip()
                value = line[ii + 1:].strip()
                sinks[sink_name][name] = value
        elif indent == 2:  # Get sink object properties
            if sinks[sink_name][name] == "":
                sinks[sink_name][name] = {}
            ii = line.index("=")
            sub_name = line[:ii].strip()
            sub_value = line[ii + 1:].strip()
            if sub_value[0] == "'" and sub_value[-1] == "'":
                sub_value = sub_value[1:-1]
            sinks[sink_name][name][sub_name] = sub_value
        else:  # Unexpected indentation
            print("Unexpected line : ", oline)
            exit()

    # eprint(json.dumps(sinks, indent=2))
    return sinks


def list_sinks():
    sinks = []
    if nwg_panel.common.commands["pamixer"]:
        try:
            output = cmd2string("pamixer --list-sinks")
            if output:
                lines = output.splitlines()[1:]
                for line in lines:
                    details = line.split()
                    name = details[1][1:-1]
                    desc = " ".join(details[3:])[1:-1]
                    sink = {"name": name, "desc": desc, "running": True if "Running" in line else False}
                    sinks.append(sink)

        except Exception as e:
            eprint(e)

    elif nwg_panel.common.commands["pactl"]:
        try:
            output = cmd2string("pactl list sinks")
            if output:
                lines = output.splitlines()
                sink = {}
                for line in lines:
                    indent = line.count("\t")
                    line = line.lstrip("\t")
                    if indent == 0 and sink:
                        sinks.append(sink)
                        sink = {}
                    elif indent == 1:
                        if line.lower().startswith("name"):
                            sink.update({"name": line.split(": ")[1]})
                        elif line.lower().startswith("description"):
                            sink.update({"desc": line.split(": ")[1]})
                        elif line.lower().startswith("state"):
                            sink.update({"running": True if "RUNNING" in line else False})
                if sink:
                    sinks.append(sink)
        except Exception as e:
            eprint(e)
    else:
        eprint("Couldn't list sinks, no 'pamixer' or 'pactl' found")

    return sinks


def toggle_mute(*args):
    if nwg_panel.common.commands["pamixer"]:
        vol, muted = get_volume()
        if muted:
            subprocess.call("pamixer -u".split())
        else:
            subprocess.call("pamixer -m".split())
    elif nwg_panel.common.commands["pactl"]:
        subprocess.call("pactl set-sink-mute @DEFAULT_SINK@ toggle".split())
    else:
        eprint("Couldn't toggle mute, no 'pamixer' or 'pactl' found")


def set_volume(percent):
    if nwg_panel.common.commands["pamixer"]:
        subprocess.call("pamixer --set-volume {}".format(percent).split())
    elif nwg_panel.common.commands["pactl"]:
        subprocess.call("pactl set-sink-volume @DEFAULT_SINK@ {}%".format(percent).split())
    else:
        eprint("Couldn't set volume, no 'pamixer' or 'pactl' found")


def get_brightness(device="", controller=""):
    brightness = 0
    if nwg_panel.common.commands["light"] and controller == "light":
        cmd = "light -G -s {}".format(device) if device else "light -G"
        output = cmd2string(cmd)
        brightness = int(round(float(output), 0))
    elif nwg_panel.common.commands["brightnessctl"] and controller == "brightnessctl":
        cmd = "brightnessctl m -d {}".format(device) if device else "brightnessctl m"
        output = cmd2string(cmd)
        max_bri = int(output)

        cmd = "brightnessctl g -d {}".format(device) if device else "brightnessctl g"
        output = cmd2string(cmd)
        b = int(output) * 100 / max_bri
        brightness = int(round(float(b), 0))
    elif nwg_panel.common.commands["ddcutil"] and controller == "ddcutil":
        cmd = "ddcutil getvcp 10 --bus={}".format(device) if device else "ddcutil getvcp 10"
        output = cmd2string(cmd)
        b = int(output.split("current value =")[1].split(",")[0])
        brightness = int(round(float(b), 0))
    else:
        raise ValueError("Couldn't get brightness, is 'light' or 'brightnessctl' or 'ddcutil' installed?")

    return brightness


def set_brightness(percent, device="", controller=""):
    if percent == 0:
        percent = 1
    if nwg_panel.common.commands["light"] and controller == "light":
        if device:
            subprocess.Popen("light -s {} -S {}".format(device, percent).split())
        else:
            subprocess.Popen("light -S {}".format(percent).split())
    elif nwg_panel.common.commands["brightnessctl"] and controller == "brightnessctl":
        if device:
            subprocess.Popen("brightnessctl -d {} s {}%".format(device, percent).split(),
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.STDOUT)
        else:
            subprocess.Popen("brightnessctl s {}%".format(percent).split(),
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.STDOUT)
    elif nwg_panel.common.commands["ddcutil"] and controller == "ddcutil":
        if device:
            subprocess.Popen("ddcutil setvcp 10 {} --bus={}".format(percent, device).split())
        else:
            subprocess.Popen("ddcutil setvcp 10 {}".format(percent).split())
    else:
        eprint("Either 'light' or 'brightnessctl' or 'ddcutil' package required")


def get_battery():
    percent, time, charging = 0, "", False
    success = False

    battery_count = len(glob.glob("/sys/class/power_supply/BAT*"))
    if battery_count <= 1:
        try:
            b = psutil.sensors_battery()
            if b:
                percent = int(round(b.percent, 0))
                charging = b.power_plugged
                seconds = b.secsleft
                if seconds != psutil.POWER_TIME_UNLIMITED and seconds != psutil.POWER_TIME_UNKNOWN:
                    time = seconds2string(seconds)
                else:
                    time = ""
                success = True
        except:
            pass

    if not success and nwg_panel.common.commands["upower"]:
        lines = subprocess.check_output(
            "LANG=en_US upower -i $(upower -e | grep devices/DisplayDevice) | grep --color=never -E 'state|to[[:space:]]full|to[[:space:]]empty|percentage'",
            shell=True).decode("utf-8").strip().splitlines()
        for line in lines:
            if "state:" in line:
                charging = line.split(":")[1].strip() == "charging"
            elif "time to" in line:
                time = line.split(":")[1].strip()
            elif "percentage:" in line:
                try:
                    percent = round(float(line.split(":")[1].strip()[:-1]))
                except:
                    pass

    return percent, time, charging


def seconds2string(seconds):
    minutes, sec = divmod(seconds, 60)
    hrs, minutes = divmod(minutes, 60)

    hrs = str(hrs)
    if len(hrs) < 2:
        hrs = "0{}".format(hrs)

    minutes = str(minutes)
    if len(minutes) < 2:
        minutes = "0{}".format(minutes)

    return "{}:{}".format(hrs, minutes)


def update_image(image, icon_name, icon_size, icons_path="", fallback=True):
    scale = image.get_scale_factor()
    icon_size *= scale
    pixbuf = create_pixbuf(icon_name, icon_size, icons_path, fallback)
    surface = Gdk.cairo_surface_create_from_pixbuf(pixbuf, scale, image.get_window())
    image.set_from_surface(surface)


def update_image_fallback_desktop(image, icon_name, icon_size, icons_path, fallback=True):
    try:
        # This should work if your icon theme provides the icon, or if it's placed in /usr/share/pixmaps
        update_image(image, icon_name, icon_size, fallback=False)
    except:
        # If the above fails, let's search .desktop files to find the icon name
        icon_from_desktop = get_icon_name(icon_name)
        if icon_from_desktop:
            # trim extension, if given and the definition is not a path
            # if "/" not in icon_from_desktop:
            #     icon_from_desktop = os.path.splitext(icon_from_desktop)[0]

            update_image(image, icon_from_desktop, icon_size, icons_path, fallback=fallback)


def update_gtk_entry(entry, icon_pos, icon_name, icon_size, icons_path=""):
    scale = entry.get_scale_factor()
    icon_size *= scale
    pixbuf = create_pixbuf(icon_name, icon_size, icons_path)
    entry.set_icon_from_pixbuf(icon_pos, pixbuf)


def create_pixbuf(icon_name, icon_size, icons_path="", fallback=True):
    try:
        # In case a full path was given
        if icon_name.startswith("/"):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                icon_name, icon_size, icon_size)
        else:
            icon_theme = Gtk.IconTheme.get_default()
            if icons_path:
                search_path = icon_theme.get_search_path()
                search_path.append(icons_path)
                icon_theme.set_search_path(search_path)

            try:
                if icons_path:
                    path = "{}/{}.svg".format(icons_path, icon_name)
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                        path, icon_size, icon_size)
                else:
                    raise ValueError("icons_path not supplied.")
            except:
                try:
                    pixbuf = icon_theme.load_icon(icon_name, icon_size, Gtk.IconLookupFlags.FORCE_SIZE)
                except:
                    pixbuf = icon_theme.load_icon(icon_name.lower(), icon_size, Gtk.IconLookupFlags.FORCE_SIZE)
    except Exception as e:
        if fallback:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                os.path.join(get_config_dir(), "icons_light/icon-missing.svg"), icon_size, icon_size)
        else:
            raise e
    return pixbuf


def list_configs(config_dir):
    configs = {}
    # allow to store json files other than panel config files in the config directory
    # (prevents from crash w/ nwg-drawer>=0.1.7 and future nwg-menu versions)
    exclusions = [os.path.join(config_dir, "preferred-apps.json"),
                  os.path.join(config_dir, "calendar.json"),
                  os.path.join(config_dir, "common-settings.json")]
    entries = os.listdir(config_dir)
    entries.sort()
    for entry in entries:
        path = os.path.join(config_dir, entry)
        if os.path.isfile(path) and path not in exclusions and not path.endswith(".css"):
            try:
                with open(path, 'r') as f:
                    config = json.load(f)
                configs[path] = config
            except:
                pass

    return configs


def get_cache_dir():
    if os.getenv("XDG_CACHE_HOME"):
        return os.getenv("XDG_CACHE_HOME")
    elif os.getenv("HOME") and os.path.isdir(os.path.join(os.getenv("HOME"), ".cache")):
        return os.path.join(os.getenv("HOME"), ".cache")
    else:
        return None

def file_age(path):
    return time.time() - os.stat(path)[stat.ST_MTIME]


def hms():
    return datetime.fromtimestamp(time.time()).strftime("%H:%M:%S")


def get_shell_data_dir():
    data_dir = ""
    home = os.getenv("HOME")
    xdg_data_home = os.getenv("XDG_DATA_HOME")

    if xdg_data_home:
        data_dir = os.path.join(xdg_data_home, "nwg-shell/")
    else:
        if home:
            data_dir = os.path.join(home, ".local/share/nwg-shell/")

    return data_dir


def load_shell_data():
    shell_data_file = os.path.join(get_shell_data_dir(), "data")
    shell_data = load_json(shell_data_file) if os.path.isfile(shell_data_file) else {}

    defaults = {
        "interface-locale": ""
    }

    for key in defaults:
        if key not in shell_data:
            shell_data[key] = defaults[key]

    return shell_data


def hyprctl(cmd, buf_size=2048):
    # /tmp/hypr moved to $XDG_RUNTIME_DIR/hypr in #5788
    xdg_runtime_dir = os.getenv("XDG_RUNTIME_DIR")
    hypr_dir = f"{xdg_runtime_dir}/hypr" if xdg_runtime_dir and os.path.isdir(
        f"{xdg_runtime_dir}/hypr") else "/tmp/hypr"

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(f"{hypr_dir}/{os.getenv('HYPRLAND_INSTANCE_SIGNATURE')}/.socket.sock")
        s.send(cmd.encode("utf-8"))

        output = b""
        while True:
            buffer = s.recv(buf_size)
            if buffer:
                output = b"".join([output, buffer])
            else:
                break
        s.close()
        return output.decode('utf-8')
    except Exception as e:
        eprint(f"hyprctl: {e}")
        return ""


def h_list_monitors():
    reply = hyprctl("j/monitors")
    try:
        return json.loads(reply)
    except Exception as e:
        eprint(e)
        return {}


def h_list_workspaces():
    reply = hyprctl("j/workspaces")
    try:
        return json.loads(reply)
    except Exception as e:
        eprint(e)
        return {}


def h_list_clients():
    reply = hyprctl("j/clients")
    try:
        return json.loads(reply)
    except Exception as e:
        eprint(e)
        return {}


def h_get_activewindow():
    reply = hyprctl("j/activewindow")
    try:
        return json.loads(reply)
    except Exception as e:
        eprint(e)
        return {}


def h_get_active_workspace():
    reply = hyprctl("j/activeworkspace")
    try:
        return json.loads(reply)
    except Exception as e:
        eprint(e)
        return {}


def h_modules_get_all():
    return h_list_monitors(), h_list_workspaces(), h_list_clients(), h_get_activewindow(), h_get_active_workspace()


def cmd_through_compositor(cmd):
    cmd = cmd.replace("\"", "'")
    cs_file = os.path.join(get_config_dir(), "common-settings.json")
    common_settings = load_json(cs_file)
    if "run-through-compositor" not in common_settings or common_settings["run-through-compositor"] :
        if os.getenv("SWAYSOCK"):
            if os.getenv("XDG_SESSION_DESKTOP") and "miracle-wm" in os.getenv("XDG_SESSION_DESKTOP"):
                cmd = f'miraclemsg exec "{cmd}"'
            else:
                cmd = f'swaymsg exec "{cmd}"'
        elif os.getenv("HYPRLAND_INSTANCE_SIGNATURE"):
            cmd = f'hyprctl dispatch exec "{cmd}"'
    return cmd


def load_resource(package, resource_name):
    try:
        import importlib.resources as resources
        with resources.open_binary(package, resource_name) as resource_file:
            return resource_file.read()
    except:
        pass
        
    try:
        import importlib.util
        spec = importlib.util.find_spec(package)
        if spec is not None and spec.loader is not None and hasattr(spec.loader, 'get_data'):
            return spec.loader.get_data(resource_name)
    except Exception:
        pass

    try:
        import pkgutil
        data = pkgutil.get_data(package, resource_name)
        if data is None:
            raise FileNotFoundError(f"Resource {resource_name} not found in package {package}.")
        return data
    except ImportError as e:
        raise ImportError("Failed to load the resource using any available method.") from e
