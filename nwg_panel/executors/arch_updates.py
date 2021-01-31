#!/usr/bin/python

import subprocess


# You may either use the full icon(s) path here, like e.g.:
# "/home/piotr/.config/nwg-panel/icons_light/arch-linux.svg"
# or just give the icon name, like below.

# The icon name must either exist in your icon theme, or you may place `icon_name.svg`
# custom files in '~/.config/nwg-panel/icons_light/' and '~/.config/nwg-panel/icons_dark/'.


def main():
    arch, aur = check_updates()
    if arch and aur:
        print("software-update-urgent")
        print("{}/{}".format(arch, aur))
    elif arch:
        print("software-update-available")
        print("{}".format(arch))
    elif aur:
        print("software-update-available")
        print("{}".format(aur))


def check_updates():
    arch, aur = 0, 0
    try:
        arch = len(subprocess.check_output(["checkupdates"]).decode("utf-8").splitlines())
    except:
        pass
    try:
        aur = len(subprocess.check_output(["trizen", "-Qqu", "-a"]).decode("utf-8").splitlines())
    except:
        pass
    return arch, aur


if __name__ == "__main__":
    main()
