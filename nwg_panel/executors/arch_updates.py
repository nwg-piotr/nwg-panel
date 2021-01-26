#!/usr/bin/python

import subprocess

# put your icons path here
icons_path = "/home/piotr/.config/nwg-panel/icons_light"


def main():
    arch, aur = check_updates()
    if arch and aur:
        print("{}/arch-linux.svg".format(icons_path))
        print("{}/{}".format(arch, aur))
    elif arch:
        print("{}/arch-linux.svg".format(icons_path))
        print("{}".format(arch))
    elif aur:
        print("{}/arch-linux.svg".format(icons_path))
        print("{}".format(aur))


def check_updates():
    arch, aur = 0, 0
    try:
        arch = len(subprocess.check_output(["pacman", "-Qqu"]).decode("utf-8").splitlines())
    except:
        pass
    try:
        aur = len(subprocess.check_output(["trizen", "-Qqu", "-a"]).decode("utf-8").splitlines())
    except:
        pass
    return arch, aur


if __name__ == "__main__":
    main()
