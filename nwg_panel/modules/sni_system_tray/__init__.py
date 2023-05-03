import typing
import multiprocessing as mp

from . import host, watcher
from .tray import Tray

watcher_process = None


def init_tray(trays: typing.List[Tray]):
    # Run host in GLib main loop
    host.init(0, trays)

    # Playerctl and tray watcher are both dbus-driven modules. Some bad media
    # players will freeze on start, because status notifier registration and
    # playerctl pulling metadata happen at the same time. Run watcher in a
    # separate process workarounds this issue.
    global watcher_process
    ctx = mp.get_context('spawn')
    watcher_process = ctx.Process(target=watcher.init, daemon=True)
    watcher_process.start()

def deinit_tray():
    global watcher_process
    if watcher_process:
        watcher_process.terminate()
