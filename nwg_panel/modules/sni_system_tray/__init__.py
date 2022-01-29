import typing
from threading import Thread

from . import host, watcher
from .tray import Tray


def init_tray(trays: typing.List[Tray]):
    host_thread = Thread(target=host.init, args=[0, trays])
    host_thread.daemon = True
    host_thread.start()

    watcher_thread = Thread(target=watcher.init)
    watcher_thread.daemon = True
    watcher_thread.start()


def deinit_tray():
    host.deinit()
    watcher.deinit()
