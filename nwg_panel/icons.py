import os

class_to_icon_cache = {}
name_to_icon_cache = {}
filename_to_icon_cache = {}


def __get_app_dirs():
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


def __process_desktop_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    icon_name = None
    app_names = []
    startup_wm_class = None
    for line in content.splitlines():
        if line.startswith("[") and line != "[Desktop Entry]":
            break
        if line.upper().startswith("ICON"):
            icon_name = line.split("=", 1)[1].strip()
        elif line.upper().startswith("NAME"):
            app_names.append(line.split("=", 1)[1].strip())
        elif line.upper().startswith("STARTUPWMCLASS"):
            startup_wm_class = line.split("=", 1)[1].strip()

    if not icon_name:
        return

    if startup_wm_class:
        if not class_to_icon_cache.get(startup_wm_class):
            class_to_icon_cache[startup_wm_class] = icon_name
        elif class_to_icon_cache.get(startup_wm_class) != icon_name:
            print(f"Warning: Duplicate class name '{startup_wm_class}' found in cache.")

    for app_name in app_names:
        if not name_to_icon_cache.get(app_name):
            name_to_icon_cache[app_name] = icon_name
        elif name_to_icon_cache.get(app_name) != icon_name:
            print(f"Warning: Duplicate app name '{app_name}' found in cache.")

    base_filename = os.path.basename(file_path).upper()
    if not filename_to_icon_cache.get(base_filename):
        filename_to_icon_cache[base_filename] = icon_name
    elif filename_to_icon_cache.get(base_filename) != icon_name:
        print(f"Warning: Duplicate .desktop file name '{base_filename}' found in cache.")


def __populate_caches():
    app_dirs = __get_app_dirs()
    seen_dirs = set()
    while app_dirs:
        d = app_dirs.pop(0)
        if d in seen_dirs:
            continue
        seen_dirs.add(d)
        if os.path.isdir(d):
            for file_name in os.listdir(d):
                file_path = os.path.realpath(os.path.join(d, file_name))
                if os.path.isdir(file_path):
                    app_dirs.insert(0, file_path)
                    continue
                __process_desktop_file(file_path)


def get_icon_name(app_name):
    if not app_name:
        return ""

    if not class_to_icon_cache and not name_to_icon_cache:
        __populate_caches()

    # Search priority: window class > app name > .desktop filename
    if app_name in class_to_icon_cache:
        return class_to_icon_cache[app_name]
    if app_name in name_to_icon_cache:
        return name_to_icon_cache[app_name]
    for filename, icon in filename_to_icon_cache.items():
        if app_name.upper() in filename:
            return icon

    # GIMP returns "app_id": null and for some reason "class": "Gimp-2.10" instead of just "gimp".
    # Until the GTK3 version is released, let's make an exception for GIMP.
    if "GIMP" in app_name.upper():
        return "gimp"

    # if all above fails, use the app_name as icon name
    return app_name
