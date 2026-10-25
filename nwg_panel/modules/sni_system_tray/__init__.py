import json
import os
import subprocess
import sys
import time
import typing

from gi.repository import GLib

from nwg_panel.tools import eprint

from . import host, watcher
from .tray import Tray

# A watcher that dies while the panel lives is started again (the items register with the new one).
# After a short delay, so that a panel which is quitting does not start one; a few times only, so that
# a watcher crashing each time does not loop forever. One that had run for a while before vanishing
# (another program's watcher that left, a crash hours apart) is not a crash loop: the count restarts.
WATCHER_RESPAWN_DELAY_S = 1
MAX_WATCHER_RESPAWNS = 5
WATCHER_STABLE_S = 60

watcher_process = None
_watcher_respawns = 0
_watcher_started = 0


def init_tray(trays: typing.List[Tray]):
    # Run host in GLib main loop
    host.init(0, trays, on_watcher_vanished)

    # Playerctl and tray watcher are both dbus-driven modules. Some bad media
    # players will freeze on start, because status notifier registration and
    # playerctl pulling metadata happen at the same time. Run watcher in a
    # separate process workarounds this issue.
    start_watcher()


# Runs watcher.py in a new interpreter with the panel's sys.path: launchers may add the dependencies to
# sys.path themselves (Nix wrappers...). -I: no PYTHONPATH, user site or script directory of its own.
# Loaded from its file, not imported: importing the sni_system_tray package would load GTK and the tray.
WATCHER_BOOTSTRAP = ("import importlib.util, json, sys; "
                     "sys.path[:] = json.loads(sys.argv[1]); "
                     "spec = importlib.util.spec_from_file_location('nwg_panel_sni_watcher', sys.argv[2]); "
                     "module = importlib.util.module_from_spec(spec); "
                     "spec.loader.exec_module(module); "
                     "module.init(int(sys.argv[3]))")


def start_watcher():
    # The watcher only needs D-Bus. A multiprocessing 'spawn' child imported the whole panel and GTK
    # again (~50 MB, plus the resource_tracker process, on a Raspberry Pi 5).
    global watcher_process, _watcher_started
    _watcher_started = time.monotonic()
    watcher_process = subprocess.Popen([sys.executable, "-I", "-c", WATCHER_BOOTSTRAP, json.dumps(sys.path),
                                        os.path.abspath(watcher.__file__), str(os.getpid())],
                                       stdin=subprocess.DEVNULL)


def on_watcher_vanished():
    GLib.timeout_add_seconds(WATCHER_RESPAWN_DELAY_S, respawn_watcher)


def respawn_watcher():
    global _watcher_respawns
    # None: deinit_tray() was called. Alive: the watcher that left was another program's, or ours is
    # still there (it exits by itself if it can't own the name).
    if time.monotonic() - _watcher_started > WATCHER_STABLE_S:
        _watcher_respawns = 0
    if watcher_process is None or watcher_process.poll() is None or _watcher_respawns >= MAX_WATCHER_RESPAWNS:
        return False
    _watcher_respawns += 1
    eprint("Tray: the StatusNotifierWatcher is gone, starting a new one")
    start_watcher()
    return False


def deinit_tray():
    global watcher_process
    if watcher_process:
        watcher_process.terminate()
        try:
            watcher_process.wait(timeout=1)  # reap it
        except subprocess.TimeoutExpired:
            watcher_process.kill()
            watcher_process.wait()
        watcher_process = None
