import json
import socket
import time

import gi

from nwg_panel import common

gi.require_version('Gtk', '3.0')
from gi.repository import GLib

from nwg_panel.tools import get_mango_socket_path

# Calculated only once when the module is imported
MANGO_SOCK_PATH = get_mango_socket_path()


def get_mango_ipc(command="get all-tags"):
    """
    Getter function to fetch the latest data from MangoWM.
    Called from within the function drawing the nwg-panel module.
    """
    if not MANGO_SOCK_PATH:
        return {}

    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect(MANGO_SOCK_PATH)

        msg = f"{command}\n"
        s.sendall(msg.encode("utf-8"))

        data = s.recv(16384).decode("utf-8", errors="replace").strip()
        s.close()

        return json.loads(data)
    except Exception as e:
        print(f"Mango IPC: Data fetch error - {e}")
        return {}


class MangoWatcher:
    """
    Pure trigger. Reacts to changes in the compositor and calls
    an empty callback (without passing data), protecting against event spam.
    """

    def __init__(self, mis, update_callback=None):
        self.update_callback = update_callback
        self.mango_sock_path = mis
        self.sock = None
        self.buffer = ""

        # Flag to prevent queuing multiple redraws in the idle loop
        self.update_queued = False

        self.start_watching()

    def start_watching(self):
        if not self.mango_sock_path:
            print("MangoWatcher: MangoWM socket not found (missing MANGO_INSTANCE_SIGNATURE)!")
            return

        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        try:
            self.sock.connect(self.mango_sock_path)
            self.sock.setblocking(False)

            # Enable continuous event stream
            self.sock.sendall(b"watch all-tags\n")

            GLib.io_add_watch(
                self.sock.fileno(),
                GLib.PRIORITY_DEFAULT,
                GLib.IOCondition.IN,
                self._handle_socket_data
            )
            print(f"MangoWatcher: Started listening on {self.mango_sock_path}")

        except Exception as e:
            print(f"MangoWatcher: Connection error - {e}")

    def _handle_socket_data(self, source, condition):
        try:
            data = self.sock.recv(16384).decode("utf-8", errors="replace")
            if not data:
                return False

            self.buffer += data
            got_event = False

            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                if line.strip():
                    got_event = True

            # Queue an update if we have new data and aren't already queued
            if got_event and not self.update_queued:
                self.update_queued = True
                GLib.idle_add(self._emit_update)

        except BlockingIOError:
            pass
        except Exception as e:
            print(f"MangoWatcher: Read error - {e}")
            return False

        return True

    def _emit_update(self):
        # Reset the flag so subsequent socket events can queue again
        self.update_queued = False

        if self.update_callback:
            self.update_callback()

        for item in common.mango_tags_list:
            all_monitors = get_mango_ipc("get all-monitors")
            all_tags = get_mango_ipc("get all-tags")
            all_clients = get_mango_ipc("get all-clients")
            item.refresh(all_monitors=all_monitors, all_tags=all_tags, all_clients=all_clients)

        # Returning False ensures idle_add removes this one-time task
        return False
