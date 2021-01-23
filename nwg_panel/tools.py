#!/usr/bin/env python3

import os
import sys
import json
import subprocess
import netifaces

import gi

gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

import common

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
    # Determine config dir path, create if not found, then create sub-dirs
    xdg_config_home = os.getenv('XDG_CONFIG_HOME')
    config_home = xdg_config_home if xdg_config_home else os.path.join(os.getenv("HOME"), ".config")
    config_dir = os.path.join(config_home, "nwg-panel")
    if not os.path.isdir(config_dir):
        print("Creating '{}'".format(config_dir))
        os.mkdir(config_dir)

    # Icon folders to store user-defined icon replacements
    icon_folder = os.path.join(config_dir, "icons_light")
    if not os.path.isdir(icon_folder):
        print("Creating '{}'".format(icon_folder))
        os.mkdir(icon_folder)

    icon_folder = os.path.join(config_dir, "icons_dark")
    if not os.path.isdir(os.path.join(icon_folder)):
        print("Creating '{}'".format(icon_folder))
        os.mkdir(icon_folder)

    return config_dir


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


def list_outputs():
    outputs = {}
    for item in common.i3.get_tree():
        if item.type == "output" and not item.name.startswith("__"):
            outputs[item.name] = {"x": item.rect.x,
                                  "y": item.rect.y,
                                  "width": item.rect.width,
                                  "height": item.rect.height}
    return outputs


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
    if common.pyalsa:
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
    if common.pyalsa:
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
    brightness = None
    output = cmd2string(common.commands["get_brightness"])
    try:
        brightness = int(round(float(output), 0))
    except:
        pass

    return brightness


def set_brightness(slider):
    value = slider.get_value()
    subprocess.call("{} {}".format(common.commands["set_brightness"], value), shell=True)


def get_battery():
    if common.upower:
        cmd = common.commands["get_battery"]
    elif common.acpi:
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
    addrs = netifaces.ifaddresses(name)
    try:
        list = addrs[netifaces.AF_INET]
        return list[0]["addr"]
    except:
        return None
