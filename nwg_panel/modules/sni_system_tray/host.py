import typing
import os

from dasbus.connection import SessionMessageBus
from dasbus.client.observer import DBusObserver
from dasbus.client.proxy import disconnect_proxy

from .watcher import WATCHER_SERVICE_NAME, WATCHER_OBJECT_PATH
from .tray import Tray
from .item import StatusNotifierItem

HOST_SERVICE_NAME_TEMPLATE = "org.kde.StatusNotifierHost-{}-{}"
HOST_OBJECT_PATH_TEMPLATE = "/StatusNotifierHost/{}"


def get_service_name_and_object_path(service: str) -> (str, str):
    index = service.find("/")
    if index != len(service):
        return service[0:index], service[index:]
    return service, "/StatusNotifierItem"


class StatusNotifierHostInterface(object):
    def __init__(self, host_id, trays: typing.List[Tray]):
        self.host_id = host_id
        self.trays = trays

        self._statusNotifierItems = []
        self.watcher_proxy = None
        self.session_bus = SessionMessageBus()

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
        if self.watcher_proxy is not None:
            disconnect_proxy(self.watcher_proxy)
        self.watcher_service_observer.disconnect()
        self.session_bus.disconnect()

    def watcher_available_handler(self, _observer):
        # print("StatusNotifierHostInterface -> watcher_available_handler")
        self.watcher_proxy = self.session_bus.get_proxy(WATCHER_SERVICE_NAME, WATCHER_OBJECT_PATH)
        self.watcher_proxy.StatusNotifierItemRegistered.connect(self.item_registered_handler)
        self.watcher_proxy.StatusNotifierItemUnregistered.connect(self.item_unregistered_handler)
        self.watcher_proxy.RegisterStatusNotifierHost(self.host_object_path, callback=lambda _: None)

        # Add items registered before host available
        for item in self.watcher_proxy.RegisteredStatusNotifierItems:
            self.item_registered_handler(item)

    def watcher_unavailable_handler(self, _observer):
        # print("StatusNotifierHostInterface -> watcher_unavailable_handler")
        self._statusNotifierItems.clear()
        disconnect_proxy(self.watcher_proxy)
        self.watcher_proxy = None

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


def init(host_id, trays: typing.List[Tray]):
    _status_notifier_host_interface = StatusNotifierHostInterface(host_id, trays)
