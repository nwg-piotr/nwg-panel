import typing
import os

from gi.repository import Gio, GLib

from dasbus.connection import SessionMessageBus
from dasbus.client.observer import DBusObserver

from nwg_panel.tools import eprint

from .watcher import WATCHER_SERVICE_NAME, WATCHER_OBJECT_PATH
from .tray import Tray
from .item import StatusNotifierItem, DBUS_TIMEOUT_MS

WATCHER_INTERFACE = "org.kde.StatusNotifierWatcher"

HOST_SERVICE_NAME_TEMPLATE = "org.kde.StatusNotifierHost-{}-{}"
HOST_OBJECT_PATH_TEMPLATE = "/StatusNotifierHost/{}"


def get_service_name_and_object_path(service: str) -> (str, str):
    index = service.find("/")
    if index != -1:
        return service[0:index], service[index:]
    return service, "/StatusNotifierItem"


class StatusNotifierHostInterface(object):
    def __init__(self, host_id, trays: typing.List[Tray], on_watcher_vanished=None):
        self.host_id = host_id
        self.trays = trays
        self.on_watcher_vanished = on_watcher_vanished

        self._statusNotifierItems = []
        self._watcher_signal_ids = []
        # bumped when the watcher goes: an answer from the previous one is then ignored
        self._watcher_generation = 0
        self.session_bus = SessionMessageBus()
        self.connection = self.session_bus.connection

        self.host_service_name = HOST_SERVICE_NAME_TEMPLATE.format(os.getpid(), self.host_id)
        self.host_object_path = HOST_OBJECT_PATH_TEMPLATE.format(self.host_id)
        self.session_bus.register_service(self.host_service_name)

        self.watcher_service_observer = DBusObserver(
            message_bus=self.session_bus,
            service_name=WATCHER_SERVICE_NAME
        )
        self.watcher_service_observer.service_available.connect(
            self.watcher_available_handler
        )
        self.watcher_service_observer.service_unavailable.connect(
            self.watcher_unavailable_handler
        )
        self.watcher_service_observer.connect_once_available()

    def __del__(self):
        self._unsubscribe_watcher()
        self.watcher_service_observer.disconnect()
        self.session_bus.disconnect()

    def watcher_available_handler(self, _observer):
        # print("StatusNotifierHostInterface -> watcher_available_handler")
        # Plain asynchronous Gio, as for the items: a dasbus proxy introspected the watcher and read
        # RegisteredStatusNotifierItems synchronously, on the GTK loop (up to 25 s if it was busy).
        # Subscribed before the read: an item registered meanwhile is announced, or in the answer.
        self._unsubscribe_watcher()
        for member, handler in (("StatusNotifierItemRegistered", self.item_registered_handler),
                                ("StatusNotifierItemUnregistered", self.item_unregistered_handler)):
            self._watcher_signal_ids.append(self.connection.signal_subscribe(
                WATCHER_SERVICE_NAME, WATCHER_INTERFACE, member, WATCHER_OBJECT_PATH, None,
                Gio.DBusSignalFlags.NONE, self._on_watcher_signal, handler))
        self._call_watcher(WATCHER_INTERFACE, "RegisterStatusNotifierHost",
                           GLib.Variant("(s)", (self.host_object_path,)), None, None)
        # Add items registered before host available
        self._call_watcher("org.freedesktop.DBus.Properties", "Get",
                           GLib.Variant("(ss)", (WATCHER_INTERFACE, "RegisteredStatusNotifierItems")),
                           GLib.VariantType("(v)"), self._on_registered_items)

    def _call_watcher(self, interface, method, parameters, reply_type, callback):
        generation = self._watcher_generation

        def on_result(connection, result, _data):
            try:
                reply = connection.call_finish(result)
            except GLib.Error as e:
                eprint(f"Tray: {method} on the watcher failed: {e.message}")
                return
            if callback is not None and generation == self._watcher_generation:
                callback(reply)

        self.connection.call(WATCHER_SERVICE_NAME, WATCHER_OBJECT_PATH, interface, method, parameters, reply_type,
                             Gio.DBusCallFlags.NONE, DBUS_TIMEOUT_MS, None, on_result, None)

    def _on_registered_items(self, reply):
        items = reply.get_child_value(0).get_variant()
        if items.get_type_string() != "as":
            return
        for item in items.unpack():
            self.item_registered_handler(item)

    @staticmethod
    def _on_watcher_signal(_connection, _sender, _path, _interface, _member, parameters, handler):
        if parameters.get_type_string() == "(s)":
            handler(parameters.unpack()[0])

    def _unsubscribe_watcher(self):
        self._watcher_generation += 1
        for signal_id in self._watcher_signal_ids:
            self.connection.signal_unsubscribe(signal_id)
        self._watcher_signal_ids.clear()

    def watcher_unavailable_handler(self, _observer):
        # print("StatusNotifierHostInterface -> watcher_unavailable_handler")
        # The next watcher re-announces the items: drop the current ones from the trays too,
        # they were left on screen, frozen.
        for item in self._statusNotifierItems:
            for tray in self.trays:
                tray.remove_item(item)
            item.destroy()
        self._statusNotifierItems.clear()
        self._unsubscribe_watcher()
        if self.on_watcher_vanished is not None:
            self.on_watcher_vanished()

    def item_registered_handler(self, full_service_service):
        """print(
            "StatusNotifierHostInterface -> item_registered_handler\n  full_service_name: {}".format(
                full_service_service
            )
        )"""
        service_name, object_path = get_service_name_and_object_path(full_service_service)
        if self.find_item(service_name, object_path) is None:
            item = StatusNotifierItem(service_name, object_path)
            item.set_on_loaded_callback(self.item_loaded_handler)
            item.set_on_updated_callback(self.item_updated_handler)
            self._statusNotifierItems.append(item)

    def item_unregistered_handler(self, full_service_service):
        """print(
            "StatusNotifierHostInterface -> item_unregistered_handler\n  full_service_name: {}".format(
                full_service_service
            )
        )"""
        service_name, object_path = get_service_name_and_object_path(full_service_service)
        item = self.find_item(service_name, object_path)
        if item is not None:
            self._statusNotifierItems.remove(item)
            for tray in self.trays:
                tray.remove_item(item)
            # release its D-Bus subscriptions and name watch: nothing else ever did
            item.destroy()

    def find_item(self, service_name, object_path) -> typing.Union[StatusNotifierItem, None]:
        for item in self._statusNotifierItems:
            if item.service_name == service_name and item.object_path == object_path:
                return item
        else:
            return None

    def item_loaded_handler(self, item):
        for tray in self.trays:
            tray.add_item(item)

    def item_updated_handler(self, item, changed_properties):
        for tray in self.trays:
            tray.update_item(item, changed_properties)


_host = None


def init(host_id, trays: typing.List[Tray], on_watcher_vanished=None):
    global _host
    _host = StatusNotifierHostInterface(host_id, trays, on_watcher_vanished)
