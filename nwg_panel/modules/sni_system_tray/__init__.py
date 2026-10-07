import typing
import multiprocessing as mp
import time

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


def start_watcher():
    global watcher_process, _watcher_started
    _watcher_started = time.monotonic()
    ctx = mp.get_context('spawn')
    watcher_process = ctx.Process(target=watcher.init, daemon=True)
    watcher_process.start()


def on_watcher_vanished():
    GLib.timeout_add_seconds(WATCHER_RESPAWN_DELAY_S, respawn_watcher)


def respawn_watcher():
    global _watcher_respawns
    # None: deinit_tray() was called. Alive: the watcher that left was another program's, or ours is
    # still there (it exits by itself if it can't own the name).
    if time.monotonic() - _watcher_started > WATCHER_STABLE_S:
        _watcher_respawns = 0
    if watcher_process is None or watcher_process.is_alive() or _watcher_respawns >= MAX_WATCHER_RESPAWNS:
        return False
    _watcher_respawns += 1
    eprint("Tray: the StatusNotifierWatcher is gone, starting a new one")
    start_watcher()
    return False


def deinit_tray():
    global watcher_process
    if watcher_process:
        watcher_process.terminate()
        watcher_process = None
